/**
 * Sending a font to the backend.
 *
 * Over HTTP rather than the WebSocket: a font is binary and a WebSocket message
 * is capped well below a CJK family's size. The backend decides whether the
 * file is a font at all; this only refuses what is obviously not one before
 * spending an upload on it.
 */

export const UPLOAD_URL = "/api/fontbook/font";

/** What the backend accepts, and what the file picker therefore offers. */
export const FONT_EXTENSIONS = [".ttf", ".otf", ".ttc", ".woff", ".woff2"];

/** A family's archive, taken whole: every font inside it is installed. */
export const ARCHIVE_EXTENSIONS = [".zip"];

/** The same caps the upload view measures, so a hopeless file is refused here
 *  rather than after sixteen megabytes have crossed the network. */
export const FONT_MAX_BYTES = 256 * 1024 * 1024;
export const ARCHIVE_MAX_BYTES = 256 * 1024 * 1024;

export function isArchive(name) {
  const lower = String(name || "").toLowerCase();
  return ARCHIVE_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

/** Why *file* cannot be sent, or `""` when it can. */
export function rejectReason(file) {
  if (!file) return "bad_type";
  const name = String(file.name || "").toLowerCase();
  const archive = isArchive(name);
  if (!archive && !FONT_EXTENSIONS.some((ext) => name.endsWith(ext))) return "bad_type";
  // A collection is a family in one file, so it is allowed an archive's size.
  const family = archive || name.endsWith(".ttc");
  if (file.size > (family ? ARCHIVE_MAX_BYTES : FONT_MAX_BYTES)) return "too_large";
  if (!file.size) return "empty";
  return "";
}

/**
 * POST one file and resolve to what the backend made of it.
 *
 * `XMLHttpRequest` and the access token by hand, because this request carries
 * no credentials of its own.
 */
export function uploadFont(hass, file) {
  const auth = hass?.auth?.accessToken || hass?.auth?.data?.access_token;
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${UPLOAD_URL}?name=${encodeURIComponent(file.name || "")}`);
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    if (auth) xhr.setRequestHeader("Authorization", `Bearer ${auth}`);
    const fail = (message, code) => {
      const err = new Error(message);
      if (code) err.code = code;
      reject(err);
    };
    xhr.onerror = () => fail("The upload could not be sent");
    xhr.onload = () => {
      let payload = null;
      try {
        payload = JSON.parse(xhr.responseText);
      } catch (_) {
        /* a body we cannot read */
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(payload || {});
        return;
      }
      fail(payload?.message || `HTTP ${xhr.status}`, payload?.code);
    };
    xhr.send(file);
  });
}

/**
 * Make *el* take dropped files, handing each one to *onFiles*.
 *
 * The zone is lit while a file is held over it; the browser would otherwise
 * open the font in place of the panel.
 */
export function wireDropZone(el, onFiles) {
  if (!el) return;
  const over = (ev) => {
    ev.preventDefault();
    if (ev.dataTransfer) ev.dataTransfer.dropEffect = "copy";
    el.classList.add("is-drop-over");
  };
  el.addEventListener("dragenter", over);
  el.addEventListener("dragover", over);
  el.addEventListener("dragleave", (ev) => {
    // Moving onto a child of the zone is still over it.
    if (ev.relatedTarget && el.contains?.(ev.relatedTarget)) return;
    el.classList.remove("is-drop-over");
  });
  el.addEventListener("drop", (ev) => {
    ev.preventDefault();
    el.classList.remove("is-drop-over");
    onFiles(Array.from(ev.dataTransfer?.files || []));
  });
}
