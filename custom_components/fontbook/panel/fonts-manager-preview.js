/**
 * Loading an installed font so a row can be drawn in it.
 *
 * `document.fonts` is the document's, not a shadow root's: a font added here is
 * usable in every row of every shadow root, which is what lets a picker style a
 * row without owning a stylesheet of its own.
 */

export const FONT_FILE_BASE = "/api/fontbook/font_file/";

/**
 * The family name a font is loaded under.
 *
 * Every character outside `A-Za-z0-9_` becomes its UTF-8 bytes in hex, so two
 * ids can never land on one family. Mirrors `alias_family` in `css.py`; the
 * two must agree exactly or a preview draws a different font than the page.
 */
export function previewFamily(fontId) {
  const encoder = new TextEncoder();
  let out = "";
  for (const char of String(fontId)) {
    if (/^[A-Za-z0-9_]$/.test(char)) {
      out += char;
      continue;
    }
    for (const byte of encoder.encode(char)) {
      out += `-${byte.toString(16).padStart(2, "0")}`;
    }
  }
  return `fonts-manager-${out}`;
}


const loaded = new Map();

/**
 * Load one font, once, and resolve to the family to draw it in.
 *
 * Resolves to `null` for a font the browser will not take -- a `.ttc`
 * collection, say -- so a caller can fall back to plain text rather than wait
 * on a face that never arrives.
 */
export function loadFontPreview(fontId, revision = "") {
  if (!fontId || !window.FontFace || !document.fonts) return Promise.resolve(null);
  const key = `${fontId}@${revision}`;
  const held = loaded.get(key);
  if (held) return held;

  const family = previewFamily(fontId);
  const query = revision ? `?r=${encodeURIComponent(revision)}` : "";
  const url = `${FONT_FILE_BASE}${encodeURIComponent(fontId)}${query}`;
  const loading = new FontFace(family, `url("${url}")`)
    .load()
    .then((face) => {
      document.fonts.add(face);
      return family;
    })
    .catch(() => {
      // Not remembered: a font that failed once, perhaps because the
      // connection dropped, is worth trying again the next time it is drawn.
      loaded.delete(key);
      return null;
    });
  loaded.set(key, loading);
  return loading;
}

/**
 * Forget the loaded faces for *fontIds*, so the next draw fetches them.
 *
 * The face is dropped from the document as well as the cache: a font installed
 * again under one id is a different file, and a face left registered under the
 * same family would keep being the one drawn.
 */
export function forgetFontPreviews(fontIds) {
  const ids = [].concat(fontIds || []).filter(Boolean);
  if (!ids.length) return;
  const families = new Set(ids.map((id) => previewFamily(id)));
  const wanted = new Set(ids);
  [...loaded.keys()]
    .filter((key) => wanted.has(key.slice(0, key.lastIndexOf("@"))))
    .forEach((key) => loaded.delete(key));
  if (!document.fonts) return;
  const stale = [];
  document.fonts.forEach((face) => {
    if (families.has(face.family)) stale.push(face);
  });
  stale.forEach((face) => document.fonts.delete(face));
}

/** Draw *el* in *fontId*'s own face once it has loaded, if it ever does. */
export function applyFontPreview(el, fontId, revision = "") {
  if (!el || !fontId) return Promise.resolve(null);
  return loadFontPreview(fontId, revision).then((family) => {
    if (family && el.isConnected) el.style.fontFamily = `"${family}"`;
    return family;
  });
}
