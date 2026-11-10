/**
 * `<fonts-manager-picker>` -- the font picker other integrations' panels use.
 *
 * Import it from the unversioned panel URL and put it in a form:
 *
 *   await import("/fontbook_panel/latest/fonts-manager-picker.js");
 *   <fonts-manager-picker .hass=${hass} value="inter-bold"></fonts-manager-picker>
 *
 * `latest` is there because a consumer cannot know the current version, which
 * is why it is the one spelling served without caching.
 *
 * `filter="emoji"` offers only the fonts that draw emoji, `filter="text"`
 * every other one; without it, all of them. The font picked stays offered
 * either way, so the field never quietly shows another.
 *
 * It fetches the font list itself over the WebSocket and emits `value-changed`
 * with `{ value }` when the user picks one, which is the convention Home
 * Assistant's own form controls follow.
 *
 * The list itself is `<fonts-manager-dropdown>`, which draws every name in its
 * own face and needs none of Home Assistant's own components: a picker that
 * fails to render is worse than one that looks ordinary.
 */

import { loadFontPreview } from "./fonts-manager-preview.js";
import "./fonts-manager-dropdown.js";

const STYLE = `
:host { display: inline-block; min-width: 220px; }
fonts-manager-dropdown { width: 100%; }
`;

export class FontsManagerPicker extends HTMLElement {
  static get observedAttributes() {
    return ["value", "disabled", "filter"];
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open", delegatesFocus: true });
    this._fonts = [];
    this._revision = "";
    this._hass = null;
    this._unsubscribe = null;
    this.shadowRoot.innerHTML =
      `<style>${STYLE}</style><fonts-manager-dropdown></fonts-manager-dropdown>`;
    this._dropdown = this.shadowRoot.querySelector("fonts-manager-dropdown");
    this._dropdown.addEventListener("value-changed", (ev) => {
      ev.stopPropagation();
      this._value = ev.detail?.value || "";
      this.dispatchEvent(new CustomEvent("value-changed", {
        detail: { value: this._value },
        bubbles: true,
        composed: true,
      }));
    });
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._subscribe();
  }

  get hass() {
    return this._hass;
  }

  set value(value) {
    this._value = value == null ? "" : String(value);
    this._render();
  }

  get value() {
    return this._value || "";
  }

  /** The font list, when a host already has it and would rather not refetch. */
  set fonts(fonts) {
    this._fonts = Array.isArray(fonts) ? fonts : [];
    this._render();
  }

  get fonts() {
    return this._fonts;
  }

  /** Which fonts to offer: `emoji`, `text`, or every one. */
  set filter(filter) {
    this._filter = filter === "emoji" || filter === "text" ? filter : "";
    this._render();
  }

  get filter() {
    return this._filter || "";
  }

  /** What the font list was when a host read it, so a replaced font redraws. */
  set revision(revision) {
    this._revision = revision || "";
    this._render();
  }

  get revision() {
    return this._revision;
  }

  attributeChangedCallback(name, _old, value) {
    if (name === "value") this.value = value;
    if (name === "disabled") this._dropdown.disabled = value !== null;
    if (name === "filter") this.filter = value;
  }

  connectedCallback() {
    // Being moved in the page closed the subscription; without this the list
    // silently stops following what is installed.
    this._subscribe();
  }

  disconnectedCallback() {
    this._unsubscribe?.then?.((off) => off?.());
    this._unsubscribe = null;
  }

  async _subscribe() {
    if (!this._hass?.connection || this._unsubscribe) return;
    this._unsubscribe = this._hass.connection.subscribeMessage(
      (message) => {
        this._fonts = message?.fonts || [];
        this._revision = message?.revision || "";
        this._render();
      },
      { type: "fontbook/subscribe" },
    ).catch(() => {
      // An older Fontbook without the subscription still lists.
      this._unsubscribe = null;
      return this._hass.callWS({ type: "fontbook/list" })
        .then((result) => {
          this._fonts = result?.fonts || [];
          this._revision = result?.revision || "";
          this._render();
        })
        .catch(() => undefined);
    });
  }

  _render() {
    if (!this._dropdown) return;
    this._dropdown.revision = this._revision;
    this._dropdown.fonts = offeredFonts(this._fonts, this.filter, this.value);
    this._dropdown.value = this.value;
  }
}

/** The fonts a picker with *filter* offers, the one picked (*value*) among them. */
export function offeredFonts(fonts, filter, value) {
  if (!filter) return fonts;
  const emoji = filter === "emoji";
  return fonts.filter((f) => Boolean(f.emoji) === emoji || f.id === value);
}

export { loadFontPreview };

if (!customElements.get("fonts-manager-picker")) {
  customElements.define("fonts-manager-picker", FontsManagerPicker);
}
