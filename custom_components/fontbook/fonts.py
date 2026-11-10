"""Which fonts are installed, what they call themselves, and where each one is.

Two places hold fonts: the directory the user uploads into
(``<ha_config>/www/fonts``) and the web fonts Home Assistant's own frontend
ships. Nothing is bundled here -- a font this integration does not have a
licence to redistribute has no business sitting in the repository.

A font's id is its file name without the extension, lowercased. That is what a
picker stores and what a consumer hands back to :func:`resolve_font_path`.

Pillow cannot read ``.woff``/``.woff2``, so those are decoded once into plain
``.ttf`` files in a cache folder and used from there; the cache follows the
source, so a removed or newer web font is dropped or redone.
"""
from __future__ import annotations

import logging
import os
import tempfile
from uuid import uuid4

from PIL import ImageFont

from .const import (
    CACHE_DIRNAME,
    CACHE_SUBDIR,
    DOMAIN,
    FONT_EXTENSIONS,
    USER_FONTS_SUBDIR,
    WEBFONT_EXTENSIONS,
)
from .metadata import font_kind, font_shape, sample_for

_LOGGER = logging.getLogger(__name__)

#: Marks a half-written conversion, so the cache sweep clears it and no
#: reader mistakes it for a finished font.
_PART_SUFFIX = ".part"

#: The size Noto Color Emoji opens at, tried when a bitmap font's own sizes
#: cannot be read. A bitmap colour font refuses every size but its strikes, so
#: probing it at a text size alone would report a good font as unreadable.
_BITMAP_PROBE_SIZE = 109


def user_fonts_dir(hass) -> str:
    """Where the user's fonts live: ``<ha_config>/www/fonts``."""
    return hass.config.path(*USER_FONTS_SUBDIR)


def webfont_cache_dir(hass) -> str:
    """Where decoded web fonts are kept, outside the user's own folder."""
    return hass.config.path(*CACHE_SUBDIR)


def list_installed(hass) -> list[dict[str, str]]:
    """Every installed font. Blocking, so call it from an executor."""
    return list_fonts(user_fonts_dir(hass), webfont_cache_dir(hass))


def resolve_installed(hass, font_id: str | None) -> str | None:
    """The file a font id names. Blocking, so call it from an executor."""
    return resolve_font_path(font_id, user_fonts_dir(hass), webfont_cache_dir(hass))


def font_id(path: str) -> str:
    """The id a font file goes by: its name without the extension, lowercased."""
    return os.path.splitext(os.path.basename(path))[0].lower()


def _files(directory: str | None, extensions: tuple[str, ...]) -> list[str]:
    """The files in *directory* with one of *extensions*, by name; hidden ones not."""
    if not directory or not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.lower().endswith(extensions) and not f.startswith(".")
    )


def font_files(directory: str | None) -> list[str]:
    """The font files in *directory* Pillow can draw with, by file name."""
    return _files(directory, FONT_EXTENSIONS)


def installed_font_files(directory: str) -> list[str]:
    """Every font file in *directory*, web fonts included.

    Unlike :func:`font_files` this hides nothing: an install has to find the
    file it is about to replace even when it is one the picker never offers.
    """
    return _files(directory, FONT_EXTENSIONS + WEBFONT_EXTENSIONS)


def _frontend_fonts_dir() -> str | None:
    """Home Assistant's own ``static/fonts``, or ``None`` when it is not there."""
    try:
        import hass_frontend  # noqa: PLC0415 - only present inside Home Assistant
        path = os.path.join(hass_frontend.where(), "static", "fonts")
    except Exception:  # noqa: BLE001 - no frontend package means no HA fonts
        return None
    return path if os.path.isdir(path) else None


def _webfont_files(directory: str | None, recursive: bool = False) -> list[str]:
    if not recursive or not directory or not os.path.isdir(directory):
        return _files(directory, WEBFONT_EXTENSIONS)
    found: list[str] = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        found.extend(
            os.path.join(root, f) for f in files
            if f.lower().endswith(WEBFONT_EXTENSIONS) and not f.startswith(".")
        )
    return sorted(found)


def decode_webfont(src: str, dst: str) -> bool:
    """Write *src* out as a plain ``.ttf`` at *dst*. ``False`` when it will not.

    The file appears at *dst* complete or not at all: a reader that finds it
    half-written would serve a broken font.
    """
    part = f"{dst}.{os.getpid()}.{uuid4().hex}{_PART_SUFFIX}"
    try:
        from fontTools.ttLib import TTFont  # noqa: PLC0415 - only needed for web fonts
        font = TTFont(src)
        font.flavor = None
        font.save(part)
        os.replace(part, dst)
    except Exception as err:  # noqa: BLE001 - a bad file must not hide the rest
        _LOGGER.warning("Web font %s cannot be converted (%s); it is not offered", src, err)
        try:
            os.remove(part)
        except OSError:
            pass
        return False
    return True


def _converted_dir(sources: list[str], cache_dir: str) -> str | None:
    """Decode *sources* into *cache_dir* and return it, dropping stale files."""
    wanted = {os.path.splitext(os.path.basename(p))[0] + ".ttf": p for p in sources}
    if os.path.isdir(cache_dir):
        for name in os.listdir(cache_dir):
            stale = name.endswith(_PART_SUFFIX) or (
                name.endswith(".ttf") and name not in wanted
            )
            if stale:
                try:
                    os.remove(os.path.join(cache_dir, name))
                except OSError:
                    pass
    if not wanted:
        return None
    os.makedirs(cache_dir, exist_ok=True)
    for name, src in wanted.items():
        dst = os.path.join(cache_dir, name)
        if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
            continue
        decode_webfont(src, dst)
    return cache_dir


def font_sources(
    user_dir: str | None, cache_dir: str | None = None
) -> list[tuple[str, str | None]]:
    """``(source, directory)`` pairs, in the order a font id is looked up.

    The user's own fonts come first, so a font they installed wins over one
    that merely happens to ship with the frontend under the same name.

    *cache_dir* holds the decoded web fonts. It is asked for rather than placed
    inside *user_dir*, which is the user's own folder and is served publicly.
    """
    base = cache_dir or os.path.join(tempfile.gettempdir(), DOMAIN + CACHE_DIRNAME)
    return [
        ("user", user_dir),
        ("user", _converted_dir(_webfont_files(user_dir), os.path.join(base, "user"))),
        ("ha", _converted_dir(
            _webfont_files(_frontend_fonts_dir(), recursive=True), os.path.join(base, "ha"))),
    ]


def font_names(path: str) -> tuple[str, str]:
    """The family and style a font file calls itself, or ``("", "")``.

    The family is what groups the weights of one family together, which is how
    a family uploaded as one archive is offered as one thing again.
    """
    # Apple Color Emoji opens at 20 to 160 but not at 109, Noto at 109 alone.
    strikes = font_kind(path).get("strikes") or []
    for size in (12, *strikes[-1:], _BITMAP_PROBE_SIZE):
        try:
            family, style = ImageFont.truetype(path, size).getname()
        except Exception:  # noqa: BLE001 - an unreadable file must not hide the rest
            continue
        family = (family or "").strip()
        if not family:
            return "", ""
        style = (style or "").strip()
        return family, "" if style.lower() == "regular" else style
    return "", ""


def display_name(path: str) -> str:
    """What the font at *path* is called in a list, or ``""`` when unreadable."""
    family, style = font_names(path)
    if not family:
        return ""
    return f"{family} {style}" if style else family


def list_fonts(
    user_dir: str | None = None, cache_dir: str | None = None
) -> list[dict[str, str]]:
    """Every installed font: ``[{"id", "name", "family", "style", "ext", "size",
    "source", "file"}]``.

    The user's fonts come first, then Home Assistant's, each sorted by file
    name. A duplicate id is left out: :func:`resolve_font_path` would answer it
    with the first file either way, so listing both would offer a choice that
    does nothing. A file Pillow cannot open is left out as well -- picking it
    would silently draw in something else.

    ``ext`` is the file's extension, lowercased, which is what tells a browser
    the format to expect and whether it can use the file at all. ``size`` is the
    file's size in bytes. ``file`` is the file's name when it sits in *user_dir*
    itself, which is the folder Home Assistant serves, and ``""`` otherwise.

    ``weight``, ``width`` and ``italic`` are what the font declares in its own
    ``OS/2`` table, and are absent when it declares nothing. They are here
    rather than in the font's metadata because the stylesheet needs them for
    every font, and the rest of the metadata only for the one being looked at.

    ``sample`` is present only for a font that cannot draw its own family name
    -- a symbol or emoji font -- and holds characters it can draw instead.

    ``emoji`` says whether the font draws emoji (it maps U+1F600 and U+1F3E0);
    ``color`` names the table it draws in colour from (``colr``, ``cbdt`` or
    ``sbix``) and ``strikes`` the pixel sizes a bitmap one opens at -- what a
    consumer needs to offer a font for emoji and to draw with it.
    """
    fonts: list[dict[str, str]] = []
    seen: set[str] = set()
    for source, directory in font_sources(user_dir, cache_dir):
        for path in font_files(directory):
            fid = font_id(path)
            if fid in seen:
                continue
            family, style = font_names(path)
            if not family:
                _LOGGER.warning("Font file %s cannot be read; it is not offered", path)
                continue
            seen.add(fid)
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            fonts.append({
                "id": fid,
                "name": f"{family} {style}" if style else family,
                "family": family,
                "style": style,
                "ext": os.path.splitext(path)[1].lower(),
                "size": size,
                "source": source,
                "file": os.path.basename(path) if directory == user_dir else "",
                **font_shape(path),
                **font_kind(path),
            })
            sample = sample_for(path, family)
            if sample:
                fonts[-1]["sample"] = sample
    return fonts


def resolve_font_path(
    name: str | None, user_dir: str | None = None, cache_dir: str | None = None
) -> str | None:
    """The file a font id names, or ``None`` when no font matches.

    The id is matched as it is written and with its spaces removed, because
    ``My Font.ttf`` is offered under the id ``my font`` and a caller may have
    reached us through either spelling. An exact match always wins, wherever it
    sits, so ``myfont`` never shadows a font genuinely called ``myfont``.
    """
    if not name:
        return None
    exact = name.lower()
    loose = exact.replace(" ", "")
    fallback: str | None = None
    for _source, directory in font_sources(user_dir, cache_dir):
        for path in font_files(directory):
            fid = font_id(path)
            if fid == exact:
                return path
            if fallback is None and fid.replace(" ", "") == loose:
                fallback = path
    return fallback
