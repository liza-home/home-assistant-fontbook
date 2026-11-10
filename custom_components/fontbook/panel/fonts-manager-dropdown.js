/**
 * `<fonts-manager-dropdown>` -- choosing a font from a list drawn in itself.
 *
 * A native `<select>` draws its popup outside the page, so `font-family` on an
 * `<option>` is ignored almost everywhere. This is a listbox of ordinary
 * elements instead, which means every name can be drawn in its own face.
 *
 * Set `fonts`, `value` and `revision`; it emits `value-changed` with
 * `{ value }`, the convention Home Assistant's own form controls follow.
 */

import { applyFontPreview, loadFontPreview } from "./fonts-manager-preview.js";

const CHEVRON = "M7.41,8.58L12,13.17L16.59,8.58L18,10L12,16L6,10L7.41,8.58Z";

const STYLE = `
:host { display: inline-block; position: relative; min-width: 220px; }
:host([hidden]) { display: none; }
button, input { font: inherit; color: inherit; }
.field {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px;
  text-align: start;
  border: 1px solid var(--divider-color, #ccc);
  border-radius: 6px;
  background: var(--card-background-color, #fff);
  color: var(--primary-text-color, #000);
  cursor: pointer;
}
.field:disabled { cursor: default; opacity: .5; }
.field:focus-visible, .search:focus-visible { outline: 2px solid var(--primary-color); }
.field .label {
  flex: 1;
  min-width: 0;
  font-size: 16px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.field svg { width: 20px; height: 20px; flex: none; fill: currentColor; }
.popup {
  position: absolute;
  z-index: 20;
  inset-inline: 0;
  margin-top: 4px;
  padding: 8px;
  border-radius: 8px;
  background: var(--card-background-color, #fff);
  color: var(--primary-text-color, #000);
  box-shadow: 0 4px 16px rgba(0, 0, 0, .25);
}
.popup[hidden] { display: none; }
.search {
  width: 100%;
  box-sizing: border-box;
  padding: 8px;
  margin-bottom: 8px;
  border: 1px solid var(--divider-color, #ccc);
  border-radius: 6px;
  background: var(--primary-background-color, #fff);
}
.list { max-height: 320px; overflow-y: auto; }
.row {
  padding: 8px;
  border-radius: 6px;
  font-size: 18px;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row:hover, .row.is-active { background: var(--divider-color, #e0e0e0); }
.row[aria-selected="true"] { color: var(--primary-color); }
.row.missing { color: var(--error-color, #db4437); }
.empty { padding: 8px; font-size: 14px; color: var(--secondary-text-color, #666); }
`;

export class FontsManagerDropdown extends HTMLElement {
  static get observedAttributes() {
    return ["value", "disabled", "aria-label"];
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open", delegatesFocus: true });
    this._fonts = [];
    this._value = "";
    this._revision = "";
    this._open = false;
    this._query = "";
    this._active = -1;
    this._options = [];
    this._paint = 0;
    this._labels = {
      search: "Search fonts",
      empty: "No font matches that.",
      missing: "missing",
      placeholder: "",
    };
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <button type="button" class="field" role="combobox"
        aria-haspopup="listbox" aria-expanded="false" aria-controls="list">
        <span class="label"></span>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="${CHEVRON}"/></svg>
      </button>
      <div class="popup" hidden>
        <input type="search" class="search" autocomplete="off" spellcheck="false"
          role="combobox" aria-controls="list" aria-expanded="true">
        <div class="list" id="list" role="listbox" tabindex="-1"></div>
      </div>`;
    this._field = this.shadowRoot.querySelector(".field");
    this._popup = this.shadowRoot.querySelector(".popup");
    this._search = this.shadowRoot.querySelector(".search");
    this._list = this.shadowRoot.querySelector(".list");

    this._field.addEventListener("click", () => this._toggle());
    this._field.addEventListener("keydown", (ev) => this._onFieldKey(ev));
    this._search.addEventListener("input", () => {
      this._query = this._search.value || "";
      this._active = -1;
      this._renderList();
    });
    this._search.addEventListener("keydown", (ev) => this._onSearchKey(ev));
    this._list.addEventListener("click", (ev) => {
      const row = ev.target.closest(".row");
      if (row) this._choose(row.dataset.value);
    });
    // A row is an ordinary div, so pressing one would blur the search field
    // and close the popup before the click could land on it.
    this._list.addEventListener("mousedown", (ev) => ev.preventDefault());
    this._onOutside = (ev) => {
      if (this._open && !ev.composedPath().includes(this)) this._close(false);
    };
    // Tabbing away must close the popup, or it hangs over whatever is below.
    // Where focus landed is only settled once the event has been dispatched.
    this.shadowRoot.addEventListener("focusout", () => {
      if (!this._open) return;
      setTimeout(() => {
        if (this._open && !this.shadowRoot.activeElement) this._close(false);
      }, 0);
    });
  }

  /** The fonts to choose from, in the order they are shown. */
  set fonts(fonts) {
    this._fonts = Array.isArray(fonts) ? fonts : [];
    this._renderAll();
  }

  get fonts() {
    return this._fonts;
  }

  set value(value) {
    this._value = value == null ? "" : String(value);
    this._renderAll();
  }

  get value() {
    return this._value;
  }

  set revision(revision) {
    this._revision = revision || "";
    this._renderAll();
  }

  get revision() {
    return this._revision;
  }

  /** What it says: `{ search, empty, missing, placeholder }`, English by default. */
  set labels(labels) {
    this._labels = { ...this._labels, ...(labels || {}) };
    this._renderAll();
  }

  get labels() {
    return this._labels;
  }

  set disabled(disabled) {
    if (disabled) this.setAttribute("disabled", "");
    else this.removeAttribute("disabled");
  }

  get disabled() {
    return this.hasAttribute("disabled");
  }

  attributeChangedCallback(name, _old, value) {
    if (name === "value") this.value = value;
    // The label belongs on the button; on the host it names nothing.
    if (name === "aria-label") {
      if (value === null) this._field.removeAttribute("aria-label");
      else this._field.setAttribute("aria-label", value);
    }
    if (name === "disabled") {
      this._field.disabled = value !== null;
      if (value !== null) this._close(false);
    }
  }

  connectedCallback() {
    document.addEventListener("click", this._onOutside, true);
    this._renderAll();
  }

  disconnectedCallback() {
    document.removeEventListener("click", this._onOutside, true);
  }

  focus() {
    this._field.focus();
  }

  _toggle() {
    if (this._open) this._close();
    else this._openPopup();
  }

  _openPopup() {
    if (this.disabled || this._open) return;
    this._open = true;
    this._query = "";
    this._search.value = "";
    this._popup.hidden = false;
    this._field.setAttribute("aria-expanded", "true");
    this._search.placeholder = this._labels.search;
    this._search.setAttribute("aria-label", this._labels.search);
    this._renderList();
    this._active = this._options.findIndex((o) => o.value === this._value);
    this._paintActive();
    this._search.focus();
  }

  _close(giveBackFocus = true) {
    if (!this._open) return;
    this._open = false;
    this._popup.hidden = true;
    this._field.setAttribute("aria-expanded", "false");
    this._search.removeAttribute("aria-activedescendant");
    if (giveBackFocus) this._field.focus();
  }

  _onFieldKey(ev) {
    if (["ArrowDown", "ArrowUp", "Enter", " "].includes(ev.key)) {
      ev.preventDefault();
      this._openPopup();
    }
  }

  _onSearchKey(ev) {
    if (ev.key === "Escape") {
      ev.preventDefault();
      ev.stopPropagation();
      this._close();
      return;
    }
    if (ev.key === "Enter") {
      ev.preventDefault();
      const option = this._options[this._active];
      if (option) this._choose(option.value);
      return;
    }
    const moves = { ArrowDown: 1, ArrowUp: -1 };
    if (ev.key in moves) {
      ev.preventDefault();
      this._move(this._active + moves[ev.key]);
      return;
    }
    if (ev.key === "Home" || ev.key === "End") {
      ev.preventDefault();
      this._move(ev.key === "Home" ? 0 : this._options.length - 1);
    }
  }

  _move(to) {
    if (!this._options.length) return;
    const last = this._options.length - 1;
    this._active = to < 0 ? last : (to > last ? 0 : to);
    this._paintActive();
  }

  _paintActive() {
    const rows = [...this._list.querySelectorAll(".row")];
    rows.forEach((row, index) => {
      row.classList.toggle("is-active", index === this._active);
    });
    const row = rows[this._active];
    if (row) {
      this._search.setAttribute("aria-activedescendant", row.id);
      row.scrollIntoView({ block: "nearest" });
    } else {
      this._search.removeAttribute("aria-activedescendant");
    }
  }

  _choose(value) {
    this._value = value == null ? "" : String(value);
    this._close();
    this._paintField();
    this.dispatchEvent(new CustomEvent("value-changed", {
      detail: { value: this._value },
      bubbles: true,
      composed: true,
    }));
  }

  /** The font behind the chosen value, or nothing when it is not installed. */
  _chosen() {
    return this.fonts.find((f) => f.id === this._value) || null;
  }

  _renderAll() {
    if (!this._field) return;
    this._paintField();
    if (this._open) this._renderList();
  }

  _paintField() {
    const label = this.shadowRoot.querySelector(".label");
    const font = this._chosen();
    const paint = ++this._paint;
    if (!this._value) {
      label.textContent = this._labels.placeholder;
      label.style.fontFamily = "";
      return;
    }
    label.textContent = font ? font.name : `${this._value} — ${this._labels.missing}`;
    if (!font) {
      label.style.fontFamily = "";
      return;
    }
    // The label outlives each repaint, so a face that arrives after the value
    // moved on would otherwise draw the new name in the old font.
    loadFontPreview(font.id, this._revision).then((family) => {
      if (family && paint === this._paint) label.style.fontFamily = `"${family}"`;
    });
  }

  _renderList() {
    this._options = listOptions({
      fonts: this._fonts,
      query: this._query,
      value: this._value,
      missing: this._labels.missing,
    });

    const html = this._options.map((option, index) => this._row(option, index)).join("");
    this._list.innerHTML = html || `<p class="empty">${esc(this._labels.empty)}</p>`;
    this._list.querySelectorAll("[data-face]").forEach((row) => {
      applyFontPreview(row, row.dataset.face, this._revision);
    });
    this._paintActive();
  }

  _row(option, index) {
    const face = option.missing ? "" : ` data-face="${esc(option.value)}"`;
    return `<div class="row${option.missing ? " missing" : ""}" role="option"`
      + ` id="fm-option-${index}" data-value="${esc(option.value)}"${face}`
      + ` aria-selected="${option.value === this._value}">${esc(option.label)}</div>`;
  }
}

/**
 * The rows a dropdown shows, as `[{ value, label, missing }]`.
 *
 * A name shared with another font is shown with its id beside it, because
 * names repeat across families often enough that the id has to disambiguate.
 */
export function listOptions({ fonts = [], query = "", value = "",
  missing = "missing" } = {}) {
  const wanted = String(query).trim().toLowerCase();
  const counts = new Map();
  fonts.forEach((f) => counts.set(f.name, (counts.get(f.name) || 0) + 1));
  const matches = (f) => !wanted
    || String(f.name).toLowerCase().includes(wanted)
    || String(f.id).toLowerCase().includes(wanted);

  const rows = fonts.filter(matches).map((font) => ({
    value: font.id,
    label: counts.get(font.name) > 1 ? `${font.name} (${font.id})` : font.name,
    missing: false,
  }));
  // A font named in a consumer's configuration but no longer installed is
  // still what is set; leaving it out would silently rewrite it.
  if (value && !wanted && !fonts.some((f) => f.id === value)) {
    rows.unshift({ value, label: `${value} — ${missing}`, missing: true });
  }
  return rows;
}

function esc(value) {
  return String(value).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

if (!customElements.get("fonts-manager-dropdown")) {
  customElements.define("fonts-manager-dropdown", FontsManagerDropdown);
}
