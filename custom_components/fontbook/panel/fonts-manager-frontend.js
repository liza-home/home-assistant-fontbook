/**
 * Put the generated font stylesheet in the document, on every page.
 *
 * Home Assistant loads this module itself, through the frontend's extra module
 * hook, which is what makes an uploaded font usable in a theme or a card rather
 * than only inside the Fontbook panel.
 *
 * The link is found and reused by id, so the module loading twice -- once as
 * the frontend's extra module, once as an import from the panel -- leaves one
 * stylesheet rather than two.
 */

export const STYLESHEET_ID = "fonts-manager-stylesheet";
export const STYLESHEET_URL = "/api/fontbook/fonts.css";

/** The `<link>` carrying the generated stylesheet, created if it is not there yet. */
export function ensureFontsStylesheet(doc = document) {
  if (!doc || !doc.head) return null;
  let link = doc.getElementById(STYLESHEET_ID);
  if (!link) {
    link = doc.createElement("link");
    link.id = STYLESHEET_ID;
    link.rel = "stylesheet";
    link.href = STYLESHEET_URL;
    link.addEventListener?.("load", () => applyInterfaceFont(doc));
    doc.head.appendChild(link);
  }
  return link;
}

/**
 * Fetch the stylesheet again, because the fonts or the interface font changed.
 *
 * The revision goes in the query rather than the server being asked not to
 * cache: the address has to actually change for the browser to treat it as a
 * new stylesheet.
 */
export function refreshFontsStylesheet(revision, doc = document) {
  const link = ensureFontsStylesheet(doc);
  if (!link) return null;
  const key = revision || String(Date.now());
  link.href = `${STYLESHEET_URL}?r=${encodeURIComponent(key)}`;
  return link;
}

/** The properties written onto `<html>`, so a cleared font can take them off again. */
const applied = new Set();

/**
 * What each property held before we first wrote it.
 *
 * Home Assistant writes its theme inline on the same element, so removing a
 * property of ours would throw the theme's value away with it.
 */
const original = new Map();

const BODY_FONT = "body:font-family";

function remember(style, name, key = name) {
  if (original.has(key)) return;
  original.set(key, {
    value: style.getPropertyValue(name),
    priority: style.getPropertyPriority(name),
  });
}

/** Take our value off *name*, leaving whatever was underneath it. */
function restore(style, name, key = name) {
  const prior = original.get(key);
  original.delete(key);
  style.removeProperty(name);
  if (prior?.value) style.setProperty(name, prior.value, prior.priority);
}

/**
 * The custom properties the generated stylesheet asks `<html>` to carry.
 *
 * Read back off our own sheet rather than kept here, so the server stays the
 * one place deciding what the interface font is.
 */
function wantedProperties(doc) {
  const wanted = new Map();
  const sheet = doc?.getElementById?.(STYLESHEET_ID)?.sheet;
  let rules;
  try {
    rules = sheet && sheet.cssRules;
  } catch {
    return wanted;
  }
  for (const rule of rules || []) {
    if (rule.selectorText !== "html" || !rule.style) continue;
    for (let i = 0; i < rule.style.length; i += 1) {
      const name = rule.style[i];
      if (name.startsWith("--")) {
        wanted.set(name, rule.style.getPropertyValue(name).trim());
      }
    }
  }
  return wanted;
}

/** Whether `<html>` has drifted from what the stylesheet asks for. */
function drifted(root, wanted) {
  for (const [name, value] of wanted) {
    if (root.style.getPropertyValue(name) !== value) return true;
    if (root.style.getPropertyPriority(name) !== "important") return true;
  }
  return false;
}

/** Whether `<body>` has drifted from the font it should be drawn in. */
function bodyDrifted(body, font) {
  if (!body?.style) return false;
  if (body.style.getPropertyValue("font-family") !== font) return true;
  return font ? body.style.getPropertyPriority("font-family") !== "important" : false;
}

/**
 * Draw `<body>` in the interface font.
 *
 * The custom properties alone reach only what asks for them by name. Home
 * Assistant's own page sets `font-family: Roboto, Noto, sans-serif` literally
 * on `body`, so the sidebar, and anything else that just inherits, never reads
 * the property. Setting the font here is what those elements follow.
 */
function applyBodyFont(body, font) {
  if (!body?.style?.setProperty) return;
  if (font) {
    remember(body.style, "font-family", BODY_FONT);
    body.style.setProperty("font-family", font, "important");
  } else {
    restore(body.style, "font-family", BODY_FONT);
  }
}

/**
 * Put the interface font on `<html>` and `<body>` themselves, at `important`.
 *
 * A plain rule in our stylesheet cannot win: Home Assistant declares the same
 * properties on the same `html` selector in an adopted sheet, which the cascade
 * orders after every linked one, and writes its theme inline on the element on
 * top of that. An inline `important` declaration beats both.
 */
export function applyInterfaceFont(doc = document) {
  const root = doc?.documentElement;
  if (!root?.style?.setProperty) return 0;

  const wanted = wantedProperties(doc);
  const font = wanted.get("--ha-font-family-body") || "";
  const stale = [...applied].filter((name) => !wanted.has(name));
  if (!stale.length && !drifted(root, wanted) && !bodyDrifted(doc.body, font)) {
    return wanted.size;
  }

  stale.forEach((name) => restore(root.style, name));
  applied.clear();
  wanted.forEach((value, name) => {
    remember(root.style, name);
    root.style.setProperty(name, value, "important");
    applied.add(name);
  });
  applyBodyFont(doc.body, font);
  return wanted.size;
}

/**
 * Put the font back whenever Home Assistant rewrites the element's style.
 *
 * `applyThemesOnElement` sets the theme inline on `<html>`, so every theme and
 * dark/light change wipes what we wrote. Re-applying is a no-op once nothing
 * has drifted, which is what stops our own writes retriggering this.
 */
export function watchInterfaceFont(doc = document) {
  const root = doc?.documentElement;
  if (!root || typeof MutationObserver === "undefined") return null;
  const observer = new MutationObserver(() => applyInterfaceFont(doc));
  observer.observe(root, { attributes: true, attributeFilter: ["style"] });
  if (doc.body) {
    observer.observe(doc.body, { attributes: true, attributeFilter: ["style"] });
  }
  return observer;
}

/**
 * Follow font changes on every page, not just the panel's.
 *
 * Without this a dashboard keeps the old font until it is reloaded, and a
 * non-admin cannot open the panel to make it catch up. The connection belongs
 * to the `home-assistant` element, which is not there the moment this module
 * loads, so it is waited for.
 */
export function watchFontChanges(doc = document, { retry = 2000 } = {}) {
  let unsubscribe = null;
  let timer = null;

  const connect = () => {
    if (unsubscribe) return true;
    const connection = doc?.querySelector?.("home-assistant")?.hass?.connection;
    if (!connection?.subscribeMessage) return false;
    unsubscribe = connection.subscribeMessage(
      (message) => {
        refreshFontsStylesheet(stylesheetKey(message), doc);
        applyInterfaceFont(doc);
      },
      { type: "fontbook/subscribe" },
    );
    unsubscribe?.catch?.(() => {
      // An older Fontbook without the subscription just means no
      // following along; the page still has the fonts it loaded with.
      unsubscribe = null;
    });
    return true;
  };

  const stop = () => {
    if (timer) clearInterval(timer);
    timer = null;
    unsubscribe?.then?.((off) => off?.());
    unsubscribe = null;
  };

  if (!connect() && typeof setInterval === "function") {
    timer = setInterval(() => {
      if (connect() && timer) {
        clearInterval(timer);
        timer = null;
      }
    }, retry);
    // Waiting for a connection is not work worth keeping a process alive for.
    timer?.unref?.();
  }
  return stop;
}

/** The query key that makes the browser treat the stylesheet as a new one. */
export function stylesheetKey(message) {
  const revision = message?.revision || "";
  const font = message?.interface_font || "none";
  return `${revision}-${font}-${message?.interface_scale ?? ""}`;
}

ensureFontsStylesheet();
applyInterfaceFont();
watchInterfaceFont();
watchFontChanges();
