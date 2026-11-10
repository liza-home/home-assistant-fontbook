"""What Fontbook serves over HTTP.

An upload, because a font is binary and a WebSocket message is capped at four
megabytes -- which a CJK family passes on its own before base64 has made it a
third larger. A font file, because the browser's font engine fetches it. A
rendered sample, because that is drawn by Pillow rather than by the browser. And
a colour emoji's picture, because not every browser draws every bitmap format.
"""
from __future__ import annotations

import logging
import os
import tempfile
from functools import partial

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .api import get_api
from .const import (
    ARCHIVE_EXTENSIONS,
    DEFAULT_SAMPLE_SIZE,
    DEFAULT_SAMPLE_TEXT,
    FONT_FILE_URL,
    FONT_GLYPH_URL,
    FONT_SAMPLE_URL,
    FONT_UPLOAD_URL,
    FONTS_CSS_URL,
    MAX_ARCHIVE_BYTES,
    MAX_FONT_BYTES,
)
from .bitmaps import glyph_png
from .css import build_stylesheet
from .fonts import (
    font_id as path_font_id,
    list_installed,
    resolve_installed,
    user_fonts_dir,
)
from .render import parse_color, render_sample
from .storage import (
    FontInstallError,
    install_font,
    install_font_archive,
    refresh_revision,
    revision,
)

_LOGGER = logging.getLogger(__name__)

_UPLOAD_CHUNK = 256 * 1024

#: What a browser must be told a font file is to use it as a web font.
_CONTENT_TYPES = {
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".ttc": "font/collection",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


def _servable_font_id(font_id: str) -> bool:
    """Whether *font_id* is an id this may look up, rather than a path.

    Ids come from :func:`font_id`, which only drops the extension and
    lowercases, so a variable font keeps its axis list, commas and all. The
    guard is therefore a path check, not an allowlist of characters.
    """
    return (
        bool(font_id)
        and font_id not in {".", ".."}
        and os.path.basename(font_id) == font_id
    )


async def _resolve_exact(hass: HomeAssistant, font_id: str) -> str | None:
    """The file *font_id* names, or ``None``.

    Exactly the id, not a name that merely resolves to it: these views' contract
    is ids alone, and the resolver is deliberately more forgiving than that.
    """
    path = await hass.async_add_executor_job(resolve_installed, hass, font_id)
    if not path or path_font_id(path) != font_id:
        return None
    return path


def _installed_ids(result: dict) -> list[str]:
    """The ids an install answer reports, single file or whole archive alike."""
    if isinstance(result.get("installed"), list):
        return [str(f.get("id")) for f in result["installed"] if f.get("id")]
    return [str(result["id"])] if result.get("id") else []


class FontUploadView(HomeAssistantView):
    """Install an uploaded font, or a whole family's zip."""

    url = FONT_UPLOAD_URL
    name = "fontbook:font"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        """Write the posted font and answer with the new font list."""
        if not request["hass_user"].is_admin:
            return web.Response(status=401)

        hass = request.app["hass"]
        filename = request.query.get("name", "")
        if not filename:
            return self.json(
                {"code": "bad_name", "message": "The file has no name"},
                status_code=400,
            )

        is_archive = filename.lower().endswith(ARCHIVE_EXTENSIONS)
        # A collection is a family in one file, so it is allowed an archive's size.
        is_family = is_archive or filename.lower().endswith(".ttc")
        cap = MAX_ARCHIVE_BYTES if is_family else MAX_FONT_BYTES

        # Streamed to a hidden file beside the fonts rather than held in memory:
        # an emoji font runs to a couple of hundred megabytes. Measured from
        # what arrived rather than from the uploader's Content-Length.
        user_dir = user_fonts_dir(hass)
        await hass.async_add_executor_job(os.makedirs, user_dir, 0o755, True)
        handle_fd, staged = await hass.async_add_executor_job(
            lambda: tempfile.mkstemp(dir=user_dir, prefix=".upload-"))
        handle = os.fdopen(handle_fd, "wb")
        try:
            received = 0
            while True:
                chunk = await request.content.read(_UPLOAD_CHUNK)
                if not chunk:
                    break
                received += len(chunk)
                if received > cap:
                    return self.json(
                        {"code": "too_large", "message": "The font is too large"},
                        status_code=413,
                    )
                await hass.async_add_executor_job(handle.write, chunk)
            await hass.async_add_executor_job(handle.close)

            install = install_font_archive if is_archive else install_font
            try:
                installed = await hass.async_add_executor_job(
                    partial(install, user_dir, filename, source_path=staged))
            except FontInstallError as err:
                _LOGGER.warning("Refused an uploaded font: %s", err)
                return self.json(
                    {"code": err.code, "message": str(err)}, status_code=400)
            except OSError as err:
                _LOGGER.exception("Failed to write an uploaded font")
                return self.json(
                    {"code": "write_failed", "message": str(err)}, status_code=500)
        finally:
            handle.close()
            if os.path.exists(staged):
                await hass.async_add_executor_job(os.remove, staged)

        await hass.async_add_executor_job(refresh_revision, user_dir)
        if (api := get_api(hass)) and _installed_ids(installed):
            api.async_notify_changed()
        fonts = await hass.async_add_executor_job(list_installed, hass)
        return self.json({**installed, "fonts": fonts})


class FontFileView(HomeAssistantView):
    """Serve one installed font so a browser can draw text in its own face.

    Unauthenticated, because a web font is fetched by the font engine, which
    carries no bearer token. Only an id :func:`resolve_installed` already knows
    is served, so there is no path to name a file outside the font directories.
    """

    url = FONT_FILE_URL
    name = "fontbook:font_file"
    requires_auth = False  # the font engine cannot send a token

    async def get(self, request: web.Request, font_id: str) -> web.StreamResponse:
        """Return the font an id names, or 404 when no font matches.

        ``?download=1`` asks for it as a file rather than a web font, which is
        how the panel hands a font back to the user who uploaded it.
        """
        if not _servable_font_id(font_id):
            return web.Response(status=404)

        path = await _resolve_exact(request.app["hass"], font_id)
        if not path:
            return web.Response(status=404)

        content_type = _CONTENT_TYPES.get(os.path.splitext(path)[1].lower())
        if not content_type:
            return web.Response(status=404)
        headers = {
            "Content-Type": content_type,
            # Replacing a font keeps its id, so the browser has to ask; the
            # file's own validators make that a cheap 304.
            "Cache-Control": "public, max-age=0, must-revalidate",
        }
        if request.query.get("download"):
            name = os.path.basename(path).replace('"', "")
            headers["Content-Disposition"] = f'attachment; filename="{name}"'
        return web.FileResponse(path, headers=headers)


class FontSampleView(HomeAssistantView):
    """Draw a line of text in one font and return it as a PNG.

    Unauthenticated for the same reason the font file is: it is an ``<img>``
    source, and the sample says nothing the font file does not already.
    """

    url = FONT_SAMPLE_URL
    name = "fontbook:sample"
    requires_auth = False  # an <img> element cannot send a token

    async def get(self, request: web.Request, font_id: str) -> web.StreamResponse:
        """Return the sample image, or 404 when no font matches."""
        if not _servable_font_id(font_id):
            return web.Response(status=404)

        hass = request.app["hass"]
        path = await _resolve_exact(hass, font_id)
        if not path:
            return web.Response(status=404)

        text = request.query.get("text") or DEFAULT_SAMPLE_TEXT
        size = request.query.get("size") or DEFAULT_SAMPLE_SIZE
        color = parse_color(request.query.get("color"))
        try:
            png = await hass.async_add_executor_job(
                render_sample, path, text, size, color)
        except (OSError, ValueError) as err:
            _LOGGER.warning("Could not draw a sample of %s: %s", font_id, err)
            return web.Response(status=404)

        return web.Response(
            body=png,
            content_type="image/png",
            headers={"Cache-Control": "public, max-age=0, must-revalidate"},
        )


class FontGlyphView(HomeAssistantView):
    """One glyph's picture from a bitmap colour font, as stored in the font.

    Unauthenticated like the sample: an ``<img>`` source, showing nothing the
    font file does not. *key* is a glyph id, or ``u`` and a code point's hex.
    """

    url = FONT_GLYPH_URL
    name = "fontbook:glyph"
    requires_auth = False  # an <img> element cannot send a token

    async def get(self, request: web.Request, font_id: str, key: str) -> web.StreamResponse:
        """Return the picture, or 404 when the font or the glyph has none."""
        if not _servable_font_id(font_id):
            return web.Response(status=404)
        hass = request.app["hass"]
        path = await _resolve_exact(hass, font_id)
        png = path and await hass.async_add_executor_job(glyph_png, path, key)
        if not png:
            return web.Response(status=404)
        # ``r`` is the font's revision: with it the address names one picture
        # for good, so the browser need not ask again.
        cache = ("public, max-age=31536000, immutable" if request.query.get("r")
                 else "public, max-age=0, must-revalidate")
        return web.Response(
            body=png, content_type="image/png", headers={"Cache-Control": cache})


class FontsStylesheetView(HomeAssistantView):
    """The generated stylesheet that makes every installed font usable.

    Unauthenticated, like the font file and the sample: the browser pulls it in
    as a stylesheet on every page, where it cannot send a token, and it says
    nothing the font list does not already.
    """

    url = FONTS_CSS_URL
    name = "fontbook:css"
    requires_auth = False  # a <link> element cannot send a token

    async def get(self, request: web.Request) -> web.Response:
        """Return the stylesheet for the fonts installed right now."""
        hass = request.app["hass"]
        fonts = await hass.async_add_executor_job(list_installed, hass)
        api = get_api(hass)
        css = build_stylesheet(
            fonts,
            revision=revision(),
            interface_font=api.interface_font if api else None,
            interface_scale=api.interface_scale if api else None,
        )
        return web.Response(
            text=css,
            content_type="text/css",
            charset="utf-8",
            # Revalidated every time: the document is rebuilt from what is on
            # disk, and a stale copy would leave a deleted font still applied.
            headers={"Cache-Control": "no-cache"},
        )


def async_register_views(hass: HomeAssistant) -> None:
    """Register the font views. Called once, from the integration's setup."""
    hass.http.register_view(FontUploadView)
    hass.http.register_view(FontFileView)
    hass.http.register_view(FontSampleView)
    hass.http.register_view(FontGlyphView)
    hass.http.register_view(FontsStylesheetView)
