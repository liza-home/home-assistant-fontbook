/**
 * `<fonts-manager-panel>` -- the sidebar panel.
 *
 * Plain custom element and template strings: the integration has no build step,
 * so the modules import each other with relative specifiers and the browser
 * resolves them against the versioned URL the backend serves them from.
 */

import { PANEL_CSS } from "./styles/panel.js";
import { translate, uiLanguage } from "./fonts-manager-i18n.js";
import {
  ARCHIVE_EXTENSIONS,
  FONT_EXTENSIONS,
  rejectReason,
  uploadFont,
  wireDropZone,
} from "./fonts-manager-upload.js";
import {
  applyFontPreview,
  forgetFontPreviews,
} from "./fonts-manager-preview.js";
import { refreshFontsStylesheet } from "./fonts-manager-frontend.js";
import "./fonts-manager-dropdown.js";

const INTERFACE_SCALE_DEFAULT = 1;
const INTERFACE_SCALE_MIN = 0.8;
const INTERFACE_SCALE_MAX = 2;
const INTERFACE_SCALE_STEP = 0.05;
const WATERFALL = [12, 16, 24, 36, 48, 72];
const TAB_STORAGE_KEY = "fonts-manager-tab";

/** `OS/2.usWidthClass` as the percentage CSS writes a width in. */
const WIDTHS = {
  1: 50, 2: 62.5, 3: 75, 4: 87.5, 5: 100, 6: 112.5, 7: 125, 8: 150, 9: 200,
};

/** How long a fact has to run before it is folded away behind a button. */
const LONG_TEXT = 160;

/** A width class as a percentage, or null when it is the normal width. */
export function widthPercent(width) {
  const percent = WIDTHS[width];
  return !percent || percent === 100 ? null : percent;
}

/**
 * *url* when it is one a link may point at, else "".
 *
 * A font carries whatever its maker wrote; `javascript:` in a vendor URL would
 * otherwise become a link the user is invited to press.
 */
export function safeUrl(url) {
  const text = String(url || "").trim();
  return /^https?:\/\//i.test(text) ? text : "";
}

/**
 * What a font's page previews it with: the alphabet and the digits, or, for a
 * font with no letters to draw, the characters it does have.
 */
export function previewLines(font) {
  if (font?.sample) return [font.sample];
  return ["ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz", "0123456789"];
}

/** A code point the way Unicode writes it: `U+1F469`. */
export function codepointLabel(code) {
  return `U+${Number(code).toString(16).toUpperCase().padStart(4, "0")}`;
}

/** Every code point of *text*, the way Unicode writes them. */
export function codepointsLabel(text) {
  return Array.from(String(text || ""), (c) => codepointLabel(c.codePointAt(0))).join(" ");
}

/**
 * Whether a character row answers to what was typed in the filter.
 *
 * Matched as a substring of its Unicode or glyph name, or as the text itself.
 * A code is matched when asked for as one -- `U+1F4` -- or by four hex digits
 * or more, since a single letter would otherwise match half of them.
 */
export function glyphMatches([text, glyph, , name], query) {
  const wanted = String(query || "").trim().toLowerCase();
  if (!wanted) return true;
  if (String(text || "").toLowerCase() === wanted) return true;
  if (String(name || "").toLowerCase().includes(wanted)) return true;
  if (String(glyph || "").toLowerCase().includes(wanted)) return true;
  const hexes = Array.from(String(text || ""),
    (c) => c.codePointAt(0).toString(16).padStart(4, "0"));
  if (wanted.startsWith("u+")) return hexes.some((hex) => hex.includes(wanted.slice(2)));
  return /^[0-9a-f]{4,}$/.test(wanted) && hexes.some((hex) => hex.includes(wanted));
}

/** Whether a font keeps its glyphs as pictures (Apple's and Google's emoji). */
export function hasGlyphImages(font) {
  return font?.color === "sbix" || font?.color === "cbdt";
}

/**
 * The address of one glyph's picture: *key* is a glyph id, or text, which is
 * looked up by its code points.
 */
export function glyphUrl(fontId, key, revision = "") {
  const part = typeof key === "number" ? String(key)
    : `u${Array.from(String(key), (c) => c.codePointAt(0).toString(16).toUpperCase()).join("-")}`;
  const query = revision ? `?r=${encodeURIComponent(revision)}` : "";
  return `/api/fontbook/glyph/${encodeURIComponent(fontId)}/${part}${query}`;
}

/**
 * *text* drawn with a bitmap font's own pictures, one per character as a
 * reader sees it, so a flag or a family is one picture. A browser that cannot
 * draw the format still shows them; spaces stay text.
 */
export function glyphImagesHtml(fontId, text, revision = "") {
  const value = String(text || "");
  const parts = typeof Intl?.Segmenter === "function"
    ? Array.from(new Intl.Segmenter().segment(value), (s) => s.segment)
    : Array.from(value);
  return parts.map((part) => (/^\s+$/.test(part) ? esc(part)
    : `<img class="glyph-img" alt="${esc(part)}" loading="lazy"
        src="${esc(glyphUrl(fontId, part, revision))}">`)).join("");
}

/** The first family named in a CSS `font-family` stack, unquoted. */
export function firstFamily(stack) {
  const first = String(stack || "").split(",")[0].trim();
  return first.replace(/^(["'])(.*)\1$/, "$2").trim();
}

/**
 * The font Home Assistant draws its interface in when none is chosen here.
 *
 * Read from the page rather than assumed, so a theme's own font shows by name.
 * One of our aliases means our override has not been taken off yet.
 */
export function defaultFontName(doc = globalThis.document) {
  let stack = "";
  try {
    stack = getComputedStyle(doc.documentElement)
      .getPropertyValue("--ha-font-family-body");
  } catch (_) {
    // No page to read from: fall through to Home Assistant's own default.
  }
  const name = firstFamily(stack);
  return name && !name.startsWith("fonts-manager-") ? name : "Roboto";
}

// Drawn as paths rather than as <ha-icon>: this module is loaded on its own
// and cannot assume the frontend's components are defined.
const ICONS = {
  menu: "M3 6h18v2H3V6m0 5h18v2H3v-2m0 5h18v2H3v-2z",
  applied: "M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2"
    + "M10,17L5,12L6.41,10.59L10,14.17L17.59,6.58L19,8L10,17Z",
  chevron: "M7.41,8.58L12,13.17L16.59,8.58L18,10L12,16L6,10L7.41,8.58Z",
  back: "M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z",
  delete: "M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19M8,9H16V19H8V9"
    + "M15.5,4L14.5,3H9.5L8.5,4H5V6H19V4H15.5Z",
  plus: "M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z",
};

/** One icon, sized by the button it sits in. */
export function icon(name) {
  return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS[name]}"/></svg>`;
}

/** A file's size in the largest unit it reaches, for showing to a person. */
export function fileSize(bytes) {
  const n = Number(bytes) || 0;
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} kB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Whether a click at *x*, *y* landed outside *box*.
 *
 * A modal dialog's backdrop is part of the dialog's own box, so a click on it
 * is reported against the dialog rather than a child. The dialog is padded,
 * though, so the target alone cannot tell the backdrop from the padding ring.
 */
export function clickedOutside(box, x, y) {
  return x < box.left || x > box.right || y < box.top || y > box.bottom;
}

/**
 * *value* as a scale the panel can offer, falling back to the default.
 *
 * Mirrors the clamp the backend applies, so the slider and the stylesheet
 * never disagree about what was asked for.
 */
export function clampScale(value) {
  const scale = Number(value);
  if (!Number.isFinite(scale)) return INTERFACE_SCALE_DEFAULT;
  return Math.min(Math.max(scale, INTERFACE_SCALE_MIN), INTERFACE_SCALE_MAX);
}

/** A scale as a percentage, which is how a person reads a size change. */
export function scaleLabel(value) {
  return `${Math.round(clampScale(value) * 100)}%`;
}

/** Where focus goes when the element that had it is replaced by a render. */
export const FOCUS_FALLBACK = {
  "interface-scale-reset": "interface-scale",
  "interface-reset": "interface-font",
};

/**
 * Put focus back where it was, since rendering replaces every element.
 *
 * A control that applies a change is rebuilt by that change, so without this a
 * second keypress would land on nothing at all.
 */
export function restoreFocus(root, id) {
  if (!root || !id) return;
  const target = root.getElementById(id)
    || (FOCUS_FALLBACK[id] ? root.getElementById(FOCUS_FALLBACK[id]) : null);
  target?.focus();
}

/**
 * Whether the panel has to offer a way back to the sidebar.
 *
 * Home Assistant's own `ha-menu-button` draws nothing while the sidebar is on
 * the screen, and a second toggle beside it is what this avoids.
 */
export function needsMenuButton(narrow, hass) {
  return Boolean(narrow) || hass?.dockedSidebar === "always_hidden";
}

export class FontsManagerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    // A character the font has no picture for is written as text instead.
    this.shadowRoot.addEventListener("error", (ev) => {
      const img = ev.target;
      if (img?.classList?.contains("glyph-img")) img.replaceWith(img.alt);
    }, true);
    this._fonts = [];
    this._revision = "";
    this._interfaceFont = null;
    this._interfaceScale = INTERFACE_SCALE_DEFAULT;
    this._language = "en";
    this._busy = false;
    this._previewText = "";
    this._detail = null;
    this._glyphFilter = "";
    this._tab = readTab();
    this._expanded = new Set();
    // What each font says about itself, once asked. Kept until the font folder
    // changes, since a replaced file keeps its id.
    this._metadata = new Map();
    this._unsubscribe = null;
    this._toastTimer = null;
    this._narrow = false;
    this._embedded = false;
  }

  static get observedAttributes() {
    return ["embedded"];
  }

  attributeChangedCallback(name) {
    if (name === "embedded") this.embedded = this.hasAttribute("embedded");
  }

  /**
   * Shown inside another panel rather than as a page of its own: just the
   * library -- no toolbar, no tabs, no way back to the sidebar -- sized by
   * whatever holds it. The interface settings stay Fontbook's own page.
   */
  set embedded(embedded) {
    const wanted = Boolean(embedded);
    if (wanted === this._embedded) return;
    this._embedded = wanted;
    this.toggleAttribute("embedded", wanted);
    this._render();
  }

  get embedded() {
    return this._embedded;
  }

  /**
   * Home Assistant's route, or a host's: `/library`, `/interface`, or
   * `/font/<id>` for that font's page. Only a path that changed is followed,
   * so the route being set again does not undo what the user opened since.
   */
  set route(route) {
    const path = typeof route?.path === "string" ? route.path : "";
    if (path === this._routePath) return;
    this._routePath = path;
    const wanted = routeTarget(path);
    if (!wanted) return;
    this._tab = wanted.tab;
    this._detail = wanted.font || null;
    this._render();
  }

  get route() {
    return { path: this._routePath || "" };
  }

  /** The tab on screen: always the library when embedded. */
  _shownTab() {
    return this._embedded ? "library" : this._tab;
  }

  set hass(hass) {
    const first = !this._hass;
    const docked = this._hass?.dockedSidebar;
    this._hass = hass;
    this._language = uiLanguage(hass);
    if (first) {
      this._render();
      this._subscribe();
    } else if (hass?.dockedSidebar !== docked) {
      this._render();
    }
  }

  get hass() {
    return this._hass;
  }

  /** Home Assistant sets this on a panel when the sidebar is off the screen. */
  set narrow(narrow) {
    const wanted = Boolean(narrow);
    if (wanted === this._narrow) return;
    this._narrow = wanted;
    this._render();
  }

  get narrow() {
    return this._narrow;
  }

  /** Whether the panel has to offer a way back to the sidebar. */
  _needsMenuButton() {
    return needsMenuButton(this._narrow, this._hass);
  }

  connectedCallback() {
    if (!this.shadowRoot.childElementCount) this._render();
    this._subscribe();
  }

  disconnectedCallback() {
    this._unsubscribe?.then?.((off) => off?.());
    this._unsubscribe = null;
  }

  _t(key, values) {
    return translate(this._language, key, values);
  }

  async _subscribe() {
    if (!this._hass?.connection || this._unsubscribe) return;
    this._unsubscribe = this._hass.connection.subscribeMessage(
      (message) => {
        this._accept(message);
        this._render();
      },
      { type: "fontbook/subscribe" },
    );
  }

  /**
   * Take a reply, and make the document's stylesheet match it.
   *
   * The stylesheet is what draws the interface, so it is refetched here rather
   * than only on the page that made the change.
   */
  _accept(message) {
    const revision = message?.revision || "";
    if (revision !== this._revision) this._metadata.clear();
    this._fonts = message?.fonts || [];
    this._revision = revision;
    this._interfaceFont = message?.interface_font || null;
    this._interfaceScale = clampScale(message?.interface_scale);
    refreshFontsStylesheet(
      `${this._revision}-${this._interfaceFont || "none"}-${this._interfaceScale}`);
  }

  async _refresh() {
    const result = await this._hass.callWS({ type: "fontbook/list" });
    this._accept(result);
    this._render();
  }

  // ── the interface font ──────────────────────────────────────────────────

  /**
   * Send *message*, take the reply, and say how it went.
   *
   * *done* turns the reply into what the toast says; *failed* is the string
   * key a refusal is reported under.
   */
  async _send(message, done, failed) {
    let result;
    try {
      result = await this._hass.callWS(message);
    } catch (err) {
      this._toast(this._t(failed, { error: this._errorText(err) }));
      return null;
    }
    this._accept(result);
    // Asked before drawing, so it can change what is drawn.
    const said = done(result);
    this._render();
    this._toast(said);
    return result;
  }

  _setInterfaceFont(fontId) {
    return this._send(
      { type: "fontbook/set_interface_font", font: fontId || null },
      () => (fontId
        ? this._t("interface_applied", { name: this._nameOf(fontId) })
        : this._t("interface_cleared")),
      "interface_failed");
  }

  /** Show a scale in the mock and the readout, without saving it. */
  _previewScale(root, value) {
    const scale = clampScale(value);
    root.getElementById("mock")?.style.setProperty("--ha-font-size-scale", scale);
    const readout = root.getElementById("interface-scale-value");
    if (readout) readout.textContent = scaleLabel(scale);
  }

  _setInterfaceScale(scale) {
    const wanted = clampScale(scale);
    return this._send(
      { type: "fontbook/set_interface_scale", scale: wanted },
      () => (wanted === INTERFACE_SCALE_DEFAULT
        ? this._t("scale_cleared")
        : this._t("scale_applied", { size: scaleLabel(wanted) })),
      "scale_failed");
  }

  _nameOf(fontId) {
    return this._fonts.find((f) => f.id === fontId)?.name || fontId;
  }

  // ── installing ──────────────────────────────────────────────────────────

  async _install(files) {
    const queue = (files || []).filter(Boolean);
    if (!queue.length || this._busy) return;
    this._busy = true;
    this._render();
    try {
      for (const file of queue) {
        await this._installOne(file);
      }
    } finally {
      this._busy = false;
      await this._refresh();
    }
  }

  async _installOne(file) {
    const refused = rejectReason(file);
    if (refused) {
      this._toast(this._t("install_failed", { error: this._t(`font_error_${refused}`) }));
      return;
    }
    let result;
    try {
      result = await uploadFont(this._hass, file);
    } catch (err) {
      this._toast(this._t("install_failed", { error: this._errorText(err) }));
      return;
    }
    // A replaced font is a new file under the same id, so whatever the browser
    // loaded for it has to go before anything is drawn again.
    forgetFontPreviews(
      Array.isArray(result.installed) ? result.installed.map((f) => f.id) : [result.id]);
    if (Array.isArray(result.installed)) {
      this._showArchiveReport(result);
      return;
    }
    this._toast(this._t(result.replaced ? "replace_done" : "install_done",
      { name: result.name || result.id }));
  }

  /** A refusal in the user's language, or the backend's sentence verbatim. */
  _errorText(err) {
    const code = err?.code;
    const key = code ? `font_error_${code}` : "";
    const said = key ? this._t(key) : "";
    return (said && said !== key ? said : "") || String(err?.message || err);
  }

  /**
   * What came of an archive, file by file.
   *
   * A toast cannot say which of sixty fonts failed, and the reason sits on the
   * individual file, so every one of them is named here.
   */
  _showArchiveReport(result) {
    const installed = result.installed || [];
    const skipped = result.skipped || [];
    const counts = this._t(installed.length ? "archive_counts" : "archive_none",
      { count: installed.length, skipped: skipped.length });
    const list = (items, titleKey, withReason) => (items.length ? `
      <h3>${esc(this._t(titleKey))}</h3>
      <ul>${items.map((f) => `<li>${esc(f.name || f.id)}${
        withReason ? `<span class="why">${esc(this._errorText(f))}</span>` : ""
      }</li>`).join("")}</ul>` : "");

    this._dialog(`
      <h3>${esc(result.archive || "")}</h3>
      <p>${esc(counts)}</p>
      ${list(installed, "archive_installed", false)}
      ${list(skipped, "archive_skipped", true)}
      <div class="actions">
        <ha-button data-close appearance="plain">${esc(this._t("close"))}</ha-button>
      </div>
    `);
  }

  // ── removing ────────────────────────────────────────────────────────────

  _confirmDelete(name, ids) {
    const dialog = this._dialog(`
      <h3>${esc(this._t("delete_confirm_title", { name }))}</h3>
      <p>${esc(this._t("delete_confirm_body"))}</p>
      <div class="actions">
        <ha-button data-close appearance="plain">${
          esc(this._t("delete_cancel"))}</ha-button>
        <ha-button data-confirm appearance="plain" variant="danger">${
          esc(this._t("delete_ok"))}</ha-button>
      </div>
    `);
    dialog.querySelector("[data-confirm]").addEventListener("click", () => {
      dialog.close();
      this._delete(ids);
    });
  }

  _delete(ids) {
    return this._send(
      { type: "fontbook/delete", fonts: ids },
      (result) => {
        forgetFontPreviews(result?.removed || ids);
        if (ids.includes(this._detail)) this._detail = null;
        return this._t("delete_done", { count: (result?.removed || []).length });
      },
      "delete_failed");
  }

  // ── drawing ─────────────────────────────────────────────────────────────

  /** Every installed font grouped by the family each file calls itself. */
  _families() {
    const byFamily = new Map();
    for (const font of this._fonts) {
      const family = font.family || font.name;
      if (!byFamily.has(family)) byFamily.set(family, { family, fonts: [] });
      byFamily.get(family).fonts.push(font);
    }
    const order = (a, b) => String(a).localeCompare(String(b));
    const families = [...byFamily.values()].sort((a, b) => order(a.family, b.family));
    families.forEach((f) => f.fonts.sort((a, b) => order(a.name, b.name)));
    return families;
  }

  /**
   * One family, drawn in itself.
   *
   * The specimen is live text rather than an image: the generated stylesheet is
   * already in the document, and `@font-face` is not scoped by a shadow root,
   * so every row can draw itself without a round trip.
   */
  _htmlFamily(entry) {
    const { family, fonts } = entry;
    const single = fonts.length === 1;
    const face = fonts.find((f) => !f.style) || fonts[0];
    const open = this._expanded.has(family);
    // Only the user's own files can be removed, so a family drawn from Home
    // Assistant's own fonts offers no Remove.
    const mine = fonts.filter((f) => f.source === "user");
    const toggle = single ? "" : `
      <button class="icon chevron${open ? " is-open" : ""}"
        type="button"
        data-expand="${esc(family)}"
        aria-expanded="${open}"
        aria-label="${esc(this._t(open ? "collapse" : "expand", { name: family }))}"
        title="${esc(this._t(open ? "collapse" : "expand", { name: family }))}"
        >${icon("chevron")}</button>`;

    return `
      <div class="family">
        <div class="frow">
          ${this._htmlSpecimen(face.id, family, "", face.sample, hasGlyphImages(face))}
          ${single ? "" : `<span class="count">${
            esc(this._t("styles", { count: fonts.length }))}</span>`}
          ${toggle}
          ${this._htmlRowActions(face, family,
            mine.length ? mine.map((f) => f.id) : null)}
        </div>
        ${single || !open ? "" : `<div class="styles">${fonts.map((font) => `
          <div class="frow is-face">
            ${this._htmlSpecimen(font.id, font.name, "face", font.sample,
              hasGlyphImages(font))}
          </div>`).join("")}</div>`}
      </div>`;
  }

  /**
   * A line of live text in one font, which clicking opens the detail of.
   *
   * *sample* stands in for the name of a font that cannot draw it -- a symbol
   * or emoji font -- so the line shows what the font holds rather than boxes.
   * The name is always written beneath, small, in the interface's own font.
   * With *images*, the line is drawn from the font's own glyph pictures.
   */
  _htmlSpecimen(fontId, label, extra = "", sample = "", images = false) {
    const text = sample || label;
    return `
      <button class="specimen ${extra}" data-detail="${esc(fontId)}"
        title="${esc(label)}">
        ${this._htmlLine(fontId, text, images)}
        <span class="who">${esc(label)}</span>
      </button>`;
  }

  /** A line of preview text in one font, which the preview field rewrites. */
  _htmlLine(fontId, text, images, style = "") {
    const attrs = [
      `class="line"`,
      style && `style="${style}"`,
      `data-face="${esc(fontId)}"`,
      images && "data-images",
      `data-specimen="${esc(text)}"`,
    ].filter(Boolean).join(" ");
    return `<span ${attrs}>${
      this._lineContent(fontId, this._previewText || text, images)}</span>`;
  }

  _lineContent(fontId, text, images) {
    return images ? glyphImagesHtml(fontId, text, this._revision) : esc(text);
  }

  /** The in-use badge, and a red Remove for the user's own fonts. */
  _htmlRowActions(font, label, deletable) {
    const on = this._interfaceFont === font.id;
    const remove = this._t("delete", { name: label });
    return `
      <div class="acts">
        ${on ? `<span class="in-use">${icon("applied")}${
          esc(this._t("in_use"))}</span>` : ""}
        ${deletable ? `<button class="icon delete" type="button"
          data-delete='${esc(JSON.stringify(deletable))}'
          data-name="${esc(label)}"
          aria-label="${esc(remove)}" title="${esc(remove)}"
          >${icon("delete")}</button>` : ""}
      </div>`;
  }

  /**
   * The rows of a font page's facts table.
   *
   * *meta* is what the font says about itself, which arrives after the page
   * does; the rows it fills are simply absent until it has. A fact the font
   * does not carry gets no row at all, since an empty row says less than none.
   */
  _facts(font, meta = {}) {
    const rows = [
      [this._t("info_family"), font.family || font.name],
      [this._t("info_style"), font.style || this._t("info_style_regular")],
      [this._t("info_id"), font.id],
      [this._t("info_format"), (font.ext || "").replace(".", "").toUpperCase()],
      [this._t("info_size"), fileSize(font.size)],
    ];
    const add = (label, value, options = {}) => {
      if (value || value === 0) rows.push([label, String(value), options]);
    };
    if (font.source !== "user") add(this._t("info_source"), this._t("info_source_ha"));
    add(this._t("info_postscript"), meta.postscript_name);
    add(this._t("info_version"), meta.version);
    add(this._t("info_weight"), font.weight ?? meta.weight);
    const stretch = widthPercent(font.width ?? meta.width);
    add(this._t("info_width"), stretch ? `${stretch}%` : "");
    add(this._t("info_glyphs"), meta.glyphs);
    add(this._t("info_designer"), meta.designer, { url: meta.vendor_url });
    add(this._t("info_copyright"), meta.copyright, { long: true });
    add(this._t("info_license"), meta.license,
      { long: true, url: meta.license_url, link: this._t("info_license_link") });
    return rows;
  }

  _htmlFacts(font, meta) {
    const anchor = (href, text) => `<a href="${esc(href)}" target="_blank"
      rel="noreferrer noopener">${esc(text)}</a>`;
    return this._facts(font, meta).map(([label, value, options = {}]) => {
      const url = safeUrl(options.url);
      let body;
      if (!options.long) {
        body = url ? anchor(url, value) : esc(value);
      } else {
        // Only text long enough to push the rest of the page down is folded.
        body = value.length > LONG_TEXT
          ? `<span class="clamp">${esc(value)}</span>
             <button class="linkish" data-reveal>${esc(this._t("info_more"))}</button>`
          : esc(value);
        if (url) body += `<div class="licence-link">${anchor(url, options.link || url)}</div>`;
      }
      return `<dt>${esc(label)}</dt><dd>${body}</dd>`;
    }).join("");
  }

  /** Ask what a font says about itself, and fill its page in with it. */
  async _loadMetadata(font, scope) {
    let meta = this._metadata.get(font.id);
    if (!meta) {
      try {
        const result = await this._hass.callWS({
          type: "fontbook/metadata", font: font.id });
        meta = result?.metadata || {};
        this._metadata.set(font.id, meta);
      } catch (_) {
        // A font with nothing to say is not an error: the page keeps the rows
        // it already drew.
        meta = {};
      }
    }
    const list = scope?.isConnected && scope.querySelector("#detail-facts");
    if (!list) return;
    list.innerHTML = this._htmlFacts(font, meta);
    list.querySelectorAll("[data-reveal]").forEach((button) =>
      button.addEventListener("click", () => {
        const open = button.previousElementSibling?.classList.toggle("is-open");
        button.textContent = this._t(open ? "info_less" : "info_more");
      }));
    this._fillCharacters(font, meta, scope);
  }

  /** The characters a font holds, as a grid that opens one on a click. */
  _fillCharacters(font, meta, scope) {
    const rows = meta.repertoire || [];
    const section = scope.querySelector("#detail-characters");
    if (!section || !rows.length) return;
    const total = meta.characters || rows.length;
    section.hidden = false;
    const count = section.querySelector(".count");
    const grid = section.querySelector(".glyphs");
    const empty = section.querySelector(".glyphs-empty");
    const filter = section.querySelector("#glyph-filter");

    const draw = () => {
      const query = this._glyphFilter;
      const shown = rows
        .map((row, index) => [row, index])
        .filter(([row]) => glyphMatches(row, query));
      count.textContent = query
        ? this._t("characters_shown", { shown: shown.length, count: rows.length })
        : total > rows.length
          ? this._t("characters_shown", { shown: rows.length, count: total })
          : String(total);
      grid.innerHTML = shown.map(([[text, glyph, glyphId, name], index]) => `
        <button class="glyph" type="button" data-glyph="${index}"
          title="${esc(text ? `${codepointsLabel(text)} ${name || ""}`.trim() : glyph)}"
          >${meta.images
            ? `<img alt="${esc(text)}" loading="lazy"
                src="${esc(glyphUrl(font.id, glyphId, this._revision))}">`
            : esc(text)}</button>`).join("");
      if (empty) empty.hidden = Boolean(shown.length);
    };

    if (filter) {
      filter.value = this._glyphFilter;
      filter.addEventListener("input", () => {
        this._glyphFilter = filter.value || "";
        draw();
      });
    }
    grid.addEventListener("click", (ev) => {
      const cell = ev.target.closest?.("[data-glyph]");
      if (cell) this._showGlyph(font, rows[Number(cell.dataset.glyph)], meta.images);
    });
    draw();
  }

  /**
   * One glyph, large, with what it is and a way to copy it. A glyph no text is
   * known for -- a variant of a bitmap emoji font -- has nothing to copy.
   */
  _showGlyph(font, row, images = false) {
    if (!row) return;
    const [char, glyph, glyphId, name] = row;
    const dialog = this._dialog(`
      <div class="glyph-card">
        ${char ? `<ha-button class="glyph-copy" data-copy-glyph appearance="filled"
          >${esc(this._t("copy"))}</ha-button>` : ""}
        <div class="glyph-big" data-face="${esc(font.id)}">${images
          ? `<img alt="${esc(char)}" src="${esc(glyphUrl(font.id, glyphId, this._revision))}">`
          : esc(char)}</div>
        <div class="glyph-meta">
          <span>${esc(glyph || "")}</span>
          <span>${glyphId ?? ""}</span>
        </div>
      </div>
      ${char ? `<div class="glyph-code">
        <span>${esc(codepointsLabel(char))}</span>
        <span>${esc(name || "")}</span>
      </div>` : ""}
      <div class="actions">
        <ha-button data-close appearance="plain">${esc(this._t("close"))}</ha-button>
      </div>
    `);
    dialog.classList.add("glyph-dialog");
    const button = dialog.querySelector("[data-copy-glyph]");
    button?.addEventListener("click", async () => {
      // Confirmed on the button itself: the toast sits beneath a modal dialog.
      if (await this._copy(char, dialog)) {
        button.textContent = this._t("copied_short");
        setTimeout(() => { button.textContent = this._t("copy"); }, 1500);
        return;
      }
      // Left selected, so ⌘C or Ctrl+C still copies it.
      const big = dialog.querySelector(".glyph-big");
      const range = document.createRange();
      range.selectNodeContents(big);
      const selection = (this.shadowRoot.getSelection?.() || window.getSelection());
      selection.removeAllRanges();
      selection.addRange(range);
    });
  }

  /**
   * Put *text* on the clipboard; whether it got there.
   *
   * The clipboard API is refused outside a secure context, which a Home
   * Assistant reached over plain http is, so the older command stands in. Its
   * scratch field goes into *container*: with a modal dialog open, everything
   * outside it is inert, and an inert field can be neither selected nor copied.
   */
  async _copy(text, container = this.shadowRoot) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      const area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      container.appendChild(area);
      area.focus();
      area.select();
      let done = false;
      try {
        done = document.execCommand("copy");
      } catch (_err) {
        done = false;
      }
      area.remove();
      return done;
    }
  }

  /** Open one font's page in place of the library list. */
  _showDetail(fontId) {
    if (!this._fonts.some((f) => f.id === fontId)) return;
    this._detail = fontId;
    this._glyphFilter = "";
    this._render();
    this.shadowRoot.getElementById("detail-back")?.focus();
    this.scrollIntoView?.({ block: "start" });
  }

  /** Back from a font's page to the library list. */
  _closeDetail() {
    const was = this._detail;
    this._detail = null;
    this._render();
    // Back where the user left off: on the line they opened.
    this.shadowRoot.querySelector(`[data-detail="${CSS?.escape?.(was) ?? was}"]`)
      ?.focus?.();
  }

  /** Everything about one font, using the whole of the library's space. */
  _htmlDetail(font) {
    const family = font.family || font.name;
    const siblings = this._fonts.filter(
      (f) => (f.family || f.name) === family && f.source === font.source);
    const text = font.sample || font.name;
    const images = hasGlyphImages(font);

    return `
      <div class="detail-head">
        <ha-icon-button id="detail-back" class="back"
          label="${esc(this._t("back"))}" title="${esc(this._t("back"))}"
          >${icon("back")}</ha-icon-button>
        <h2 ${font.sample ? "" : `data-face="${esc(font.id)}"`}>${esc(font.name)}</h2>
        ${font.source === "user" ? `<button class="icon delete" type="button"
          data-delete='${esc(JSON.stringify([font.id]))}'
          data-name="${esc(font.name)}"
          aria-label="${esc(this._t("delete", { name: font.name }))}"
          title="${esc(this._t("delete", { name: font.name }))}"
          >${icon("delete")}</button>` : ""}
      </div>
      <ha-card>
        <div class="card-content detail" id="detail">
        <h4>${esc(this._t("detail_preview"))}</h4>
        <div class="alphabet" data-face="${esc(font.id)}">${
          previewLines(font).map((line) =>
            `<div>${this._lineContent(font.id, line, images)}</div>`).join("")}</div>

        <ha-input type="text" class="specimen-text" id="detail-text"
          appearance="outlined"
          value="${esc(this._previewText)}"
          placeholder="${esc(this._t("preview_placeholder"))}"
          label="${esc(this._t("preview_text_label"))}"></ha-input>

        <h4>${esc(this._t("detail_sizes"))}</h4>
        <div class="waterfall">${WATERFALL.map((size) => `
          <div class="drop-line">
            <span class="px">${size}</span>
            ${this._htmlLine(font.id, text, images, `font-size:${size}px`)}
          </div>`).join("")}</div>

        ${siblings.length > 1 ? `
        <h4>${esc(this._t("detail_styles"))}</h4>
        <div class="styles">${siblings.map((f) => `
          <div class="drop-line">
            <span class="px">${esc(f.style || this._t("info_style_regular"))}</span>
            ${this._htmlLine(f.id, f.sample || f.name, hasGlyphImages(f))}
          </div>`).join("")}</div>` : ""}

        <h4>${esc(this._t("detail_facts"))}</h4>
        <dl class="info" id="detail-facts">${this._htmlFacts(font)}</dl>

        <section id="detail-characters" hidden>
          <div class="glyphs-head">
            <h4>${esc(this._t("detail_characters"))}
              <span class="count"></span></h4>
            <ha-input-search id="glyph-filter" appearance="outlined"
              placeholder="${esc(this._t("glyph_filter"))}"
              aria-label="${esc(this._t("glyph_filter"))}"></ha-input-search>
          </div>
          <div class="glyphs" data-face="${esc(font.id)}"></div>
          <p class="hint glyphs-empty" hidden>${esc(this._t("glyph_filter_empty"))}</p>
        </section>
        </div>
      </ha-card>`;
  }

  /** The fonts a browser can actually load: a .ttc collection cannot be. */
  _servableFonts() {
    return this._fonts.filter((f) => f.ext !== ".ttc");
  }

  _htmlInterface() {
    const servable = this._servableFonts();
    return `
      <ha-card header="${esc(this._t("interface_heading"))}">
        <div class="card-content">
          <div class="setting">
            <span class="setting-label">${esc(this._t("interface_font_label"))}</span>
            <div class="interface-controls">
              <fonts-manager-dropdown id="interface-font"
                ${servable.length ? "" : "disabled"}
                aria-label="${esc(this._t("interface_font_label"))}"></fonts-manager-dropdown>
              ${this._interfaceFont
                ? `<ha-button id="interface-reset" appearance="plain">${
                    esc(this._t("interface_reset"))}</ha-button>`
                : ""}
            </div>
          </div>
          ${this._htmlScale()}
        </div>
      </ha-card>
      ${this._htmlMock()}`;
  }

  /** Fill the interface font dropdown, which every render rebuilds. */
  _fillInterfaceDropdown(dropdown) {
    dropdown.labels = {
      search: this._t("search_placeholder"),
      empty: this._t("search_empty"),
      missing: this._t("font_missing"),
      placeholder: defaultFontName(),
    };
    dropdown.revision = this._revision;
    dropdown.fonts = this._servableFonts();
    dropdown.value = this._interfaceFont || "";
  }

  /**
   * The control that sizes the interface's text.
   *
   * Bounded on purpose: a scale large enough to push this control off the
   * screen would take with it the only way back.
   */
  _htmlScale() {
    const scale = this._interfaceScale;
    const isDefault = scale === INTERFACE_SCALE_DEFAULT;
    return `
      <div class="setting">
        <span class="setting-label">${esc(this._t("scale_heading"))}</span>
        <div class="interface-controls">
          <ha-slider id="interface-scale"
            min="${INTERFACE_SCALE_MIN}" max="${INTERFACE_SCALE_MAX}"
            step="${INTERFACE_SCALE_STEP}" value="${scale}" size="m"
            aria-label="${esc(this._t("scale_heading"))}">
          </ha-slider>
          <output id="interface-scale-value">${esc(scaleLabel(scale))}</output>
          ${isDefault
            ? ""
            : `<ha-button id="interface-scale-reset" appearance="plain">${
                esc(this._t("interface_reset"))}</ha-button>`}
        </div>
      </div>`;
  }

  /**
   * A stand-in for the interface, drawn in whatever is chosen.
   *
   * Everything here inherits the properties the stylesheet sets, so this shows
   * the real effect rather than an imitation of it -- including the code line,
   * which stays monospaced because that property is deliberately left alone.
   */
  _htmlMock() {
    const face = this._interfaceFont
      ? `data-face="${esc(this._interfaceFont)}"`
      : "";
    return `
      <ha-card header="${esc(this._t("mock_heading"))}">
        <div class="card-content">
        <div class="mock" id="mock" style="--ha-font-size-scale: ${
          this._interfaceScale}">
          <div class="mock-side" ${face}>
            <div class="mock-brand">${esc(this._t("mock_sidebar"))}</div>
            <div class="mock-item is-on">${esc(this._t("mock_overview"))}</div>
            <div class="mock-item">${esc(this._t("mock_settings"))}</div>
          </div>
          <div class="mock-main" ${face}>
            <div class="mock-card">
              <h3>${esc(this._t("mock_card"))}</h3>
              <div class="mock-reading">${esc(this._t("mock_reading"))}</div>
              <p>${esc(this._t("mock_body"))}</p>
              <code>${esc(this._t("mock_code"))}</code>
            </div>
          </div>
        </div>
        </div>
      </ha-card>`;
  }

  _htmlDropzone() {
    const label = this._t(this._busy ? "installing" : "dropzone");
    return `
      <button class="dropzone${this._busy ? " is-busy" : ""}"
        id="add" type="button">
        ${icon("plus")}
        <span class="dz-label">${esc(label)}</span>
      </button>`;
  }

  /** The font whose page is open in the library, or nothing. */
  _detailFont() {
    if (this._shownTab() !== "library" || !this._detail) return null;
    return this._fonts.find((f) => f.id === this._detail) || null;
  }

  _htmlLibrary() {
    const font = this._detailFont();
    if (font) return this._htmlDetail(font);
    const families = this._families();
    return `
      ${this._htmlDropzone()}
      ${families.length ? `<ha-card>
        <div class="card-content">
        ${families.map((f) => this._htmlFamily(f)).join("")}
        </div>
      </ha-card>` : ""}`;
  }

  _render() {
    if (!this.shadowRoot) return;
    const focused = this.shadowRoot.activeElement?.id;
    const accept = FONT_EXTENSIONS.concat(ARCHIVE_EXTENSIONS).join(",");
    const tab = (name) => `
      <ha-tab-group-tab slot="nav" panel="${name}"
        ${this._tab === name ? "active" : ""}>${esc(this._t(`tab_${name}`))}
      </ha-tab-group-tab>`;

    const menu = !this._embedded && this._needsMenuButton();
    const toolbar = this._embedded ? "" : `
      <div class="toolbar">
        <div class="toolbar-content">
          ${menu ? `<ha-icon-button class="menu" id="menu"
            label="${esc(this._t("menu"))}">${icon("menu")}</ha-icon-button>` : ""}
          <ha-tab-group class="tabs" id="tabs" tab-only>
            ${tab("library")}${tab("interface")}
          </ha-tab-group>
          ${menu ? `<div class="toolbar-end"></div>` : ""}
        </div>
      </div>`;
    this._frame().innerHTML = `${toolbar}
      <h1 class="visually-hidden">${esc(this._t("title"))}</h1>
      <div class="wrap${this._detailFont() ? " is-wide" : ""}" id="wrap">
        ${this._shownTab() === "interface" ? this._htmlInterface() : this._htmlLibrary()}
      </div>
      <input type="file" id="pick" accept="${esc(accept)}" multiple>`;

    this._wire();
    restoreFocus(this.shadowRoot, focused);
  }

  /**
   * The container a render replaces, built once.
   *
   * Dialogs and the live region sit beside it rather than inside it, so a
   * reply arriving mid-task cannot take away what the user is reading.
   */
  _frame() {
    const root = this.shadowRoot;
    let app = root.getElementById("app");
    if (app) return app;
    root.innerHTML = `
      <style>${PANEL_CSS}</style>
      <div id="app"></div>
      <output class="toast" id="toast" role="status" hidden></output>`;
    app = root.getElementById("app");
    return app;
  }

  _wire() {
    const root = this.shadowRoot;
    root.getElementById("menu")?.addEventListener("click", () => {
      // What Home Assistant's own menu button fires. It has to leave the
      // shadow root to reach the listener on the main element.
      this.dispatchEvent(new CustomEvent("hass-toggle-menu", {
        bubbles: true,
        composed: true,
      }));
    });

    root.getElementById("tabs")?.addEventListener("wa-tab-show", (ev) => {
      const tab = ev.detail?.name;
      if (!["interface", "library"].includes(tab) || tab === this._tab) return;
      this._tab = tab;
      writeTab(tab);
      this._render();
    });

    const wrap = root.getElementById("wrap");
    const pick = root.getElementById("pick");
    if (wrap && pick) {
      wireDropZone(wrap, (files) => this._install(files));
      const add = root.getElementById("add");
      if (add) {
        add.addEventListener("click", () => pick.click());
        wireDropZone(add, (files) => this._install(files));
      }
      pick.addEventListener("change", () => {
        const files = Array.from(pick.files || []);
        // Cleared first: picking the same file twice in a row still fires.
        pick.value = "";
        this._install(files);
      });
    }

    root.querySelectorAll("[data-expand]").forEach((button) => {
      button.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const family = button.dataset.expand;
        if (this._expanded.has(family)) this._expanded.delete(family);
        else this._expanded.add(family);
        this._render();
      });
    });

    root.querySelectorAll("[data-detail]").forEach((button) => {
      button.addEventListener("click", () => this._showDetail(button.dataset.detail));
    });

    root.querySelectorAll("[data-delete]").forEach((button) => {
      button.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._confirmDelete(button.dataset.name || "", JSON.parse(button.dataset.delete));
      });
    });

    root.getElementById("detail-back")?.addEventListener("click", () =>
      this._closeDetail());
    const detailText = root.getElementById("detail-text");
    if (detailText) {
      detailText.value = this._previewText;
      detailText.addEventListener("input", () => {
        this._previewText = detailText.value || "";
        this._paintPreview();
      });
    }
    const detail = root.getElementById("detail");
    const shown = detail && this._fonts.find((f) => f.id === this._detail);
    if (shown) this._loadMetadata(shown, detail);

    const pickInterface = root.getElementById("interface-font");
    if (pickInterface) {
      this._fillInterfaceDropdown(pickInterface);
      pickInterface.addEventListener("value-changed", (ev) => {
        ev.stopPropagation();
        this._setInterfaceFont(ev.detail?.value || null);
      });
    }
    root.getElementById("interface-reset")?.addEventListener("click", () => {
      this._setInterfaceFont(null);
    });

    const scale = root.getElementById("interface-scale");
    // Repainted on every move but written only on release, so dragging stays
    // responsive without a round trip for each step.
    if (scale) {
      scale.min = INTERFACE_SCALE_MIN;
      scale.max = INTERFACE_SCALE_MAX;
      scale.step = INTERFACE_SCALE_STEP;
      scale.value = this._interfaceScale;
      scale.addEventListener("input", () => {
        this._previewScale(root, scale.value);
      });
      scale.addEventListener("change", () => {
        this._setInterfaceScale(scale.value);
      });
    }
    root.getElementById("interface-scale-reset")?.addEventListener("click", () => {
      this._setInterfaceScale(INTERFACE_SCALE_DEFAULT);
    });

    this._paintFaces(root);
    this._paintPreview();
  }

  /** Draw every line marked with a font in that font. */
  _paintFaces(scope) {
    scope.querySelectorAll("[data-face]").forEach((el) => {
      applyFontPreview(el, el.dataset.face, this._revision);
    });
  }

  /**
   * Put the preview text on the lines directly.
   *
   * Rendering again on every keystroke would rebuild the page and lose the
   * caret, so the text is written onto the lines in place.
   */
  _paintPreview(scope = this.shadowRoot) {
    scope.querySelectorAll("[data-specimen]").forEach((el) => {
      const text = this._previewText || el.dataset.specimen;
      if (el.hasAttribute("data-images")) {
        el.innerHTML = this._lineContent(el.dataset.face, text, true);
      } else {
        el.textContent = text;
      }
    });
  }

  _dialog(inner) {
    const dialog = document.createElement("dialog");
    dialog.innerHTML = inner;
    dialog.addEventListener("close", () => dialog.remove());
    dialog.addEventListener("click", (ev) => {
      if (ev.target !== dialog) return;
      if (clickedOutside(dialog.getBoundingClientRect(), ev.clientX, ev.clientY)) {
        dialog.close();
      }
    });
    dialog.querySelectorAll("[data-close]").forEach((button) =>
      button.addEventListener("click", () => dialog.close()));
    this._paintFaces(dialog);
    this.shadowRoot.appendChild(dialog);
    dialog.showModal();
    return dialog;
  }

  _toast(message) {
    const toast = this.shadowRoot?.getElementById("toast");
    if (!toast) return;
    // The region is in the page from the first render, so a reader announces
    // a change to it. One created along with its text is often missed.
    clearTimeout(this._toastTimer);
    toast.textContent = message;
    toast.hidden = false;
    this._toastTimer = setTimeout(() => {
      toast.textContent = "";
      toast.hidden = true;
    }, 4000);
  }
}

/** What a route path opens: `{tab, font}`, or `null` for nothing in particular. */
export function routeTarget(path) {
  const parts = String(path || "").split("/").filter(Boolean);
  if (parts[0] === "interface") return { tab: "interface" };
  if (parts[0] === "library") return { tab: "library" };
  if (parts[0] === "font" && parts[1]) {
    let font = parts[1];
    try { font = decodeURIComponent(font); } catch (_) { /* as written */ }
    return { tab: "library", font };
  }
  return null;
}

/**
 * The tab last looked at.
 *
 * Storage can throw outright in a locked-down browser, so a failure here just
 * means the panel opens on the library.
 */
export function readTab() {
  try {
    return localStorage.getItem(TAB_STORAGE_KEY) === "interface"
      ? "interface"
      : "library";
  } catch (_) {
    return "library";
  }
}

export function writeTab(tab) {
  try {
    localStorage.setItem(TAB_STORAGE_KEY, tab);
  } catch (_) {
    // Nothing to do: the tab simply will not be remembered.
  }
}

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

if (!customElements.get("fonts-manager-panel")) {
  customElements.define("fonts-manager-panel", FontsManagerPanel);
}
