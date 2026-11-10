"""What a font file says about itself, beyond its family and style.

Pillow offers only the family and the style name, which is enough to list a
font and nothing more. The ``name`` and ``OS/2`` tables carry what a person
actually wants to know -- who made it, what it may be used for -- and, more
importantly, the weight and width the font declares, rather than the ones
guessed from a style string that no format obliges to be conventional.

``fontTools`` is already here for web-font decoding, so nothing new is pulled
in. Every read blocks on the disk, so callers stay in an executor.
"""
from __future__ import annotations

import logging
import os
import unicodedata
from typing import Any

from .bitmaps import bitmap_font

_LOGGER = logging.getLogger(__name__)

#: The ``name`` table records worth showing, by the field they become.
_NAME_IDS: tuple[tuple[str, int], ...] = (
    ("copyright", 0),
    ("full_name", 4),
    ("version", 5),
    ("postscript_name", 6),
    ("trademark", 7),
    ("designer", 9),
    ("vendor_url", 11),
    ("license", 13),
    ("license_url", 14),
)

#: ``OS/2.usWidthClass`` as the percentage CSS writes a width in.
_WIDTHS: dict[int, float] = {
    1: 50, 2: 62.5, 3: 75, 4: 87.5, 5: 100, 6: 112.5, 7: 125, 8: 150, 9: 200,
}

#: ``OS/2.fsSelection`` bit 0 and ``head.macStyle`` bit 1 both mean italic.
_FS_SELECTION_ITALIC = 1 << 0
_MAC_STYLE_ITALIC = 1 << 1

#: Past this the cache is dropped whole. A font folder is tens of files, so
#: reaching it means something is wrong rather than something is large.
_CACHE_LIMIT = 512

_cache: dict[tuple[str, int, int], dict[str, Any]] = {}

#: The most characters sent for one font. An emoji font has a few thousand; a
#: CJK font tens of thousands, which no grid is worth.
REPERTOIRE_LIMIT = 4096

#: How many characters stand in for a name the font cannot draw.
SAMPLE_LENGTH = 12

#: What makes a font an emoji font: a face and a house, from the two blocks
#: every emoji font covers and no text font does.
EMOJI_PROBES: tuple[int, ...] = (0x1F600, 0x1F3E0)

#: The tables a colour font draws its colours from, by the name a consumer
#: is told. A bitmap format (CBDT, sbix) opens at its own sizes only.
_COLOR_TABLES: tuple[tuple[str, str], ...] = (
    ("COLR", "colr"), ("CBDT", "cbdt"), ("sbix", "sbix"),
)

#: Categories with nothing to see: controls, formats, surrogates and spaces.
_INVISIBLE = {"Cc", "Cf", "Cs", "Zs", "Zl", "Zp"}


def _cache_key(path: str) -> tuple[str, int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return path, stat.st_mtime_ns, stat.st_size


def _clean(value: object) -> str:
    """*value* as a single-line string, or ``""`` when there is nothing in it."""
    return " ".join(str(value or "").split())


def _version(value: str) -> str:
    """A version string as its number alone.

    A font writes ``Version 1.001;FOO;otf.5.6.0``, of which only the number is
    worth a row in a table.
    """
    text = _clean(value)
    if text.lower().startswith("version "):
        text = text[len("version "):]
    return text.split(";")[0].strip()


def _names(font) -> dict[str, str]:
    table = font.get("name")
    if table is None:
        return {}
    found: dict[str, str] = {}
    for field, name_id in _NAME_IDS:
        try:
            raw = table.getDebugName(name_id)
        except Exception:  # noqa: BLE001 - one bad record must not lose the rest
            continue
        text = _version(raw) if field == "version" else _clean(raw)
        if text:
            found[field] = text
    return found


def _shape(font) -> dict[str, Any]:
    """The weight, width and slant the font declares."""
    found: dict[str, Any] = {}
    os2 = font.get("OS/2")
    if os2 is not None:
        weight = getattr(os2, "usWeightClass", None)
        if type(weight) is int and 1 <= weight <= 1000:
            found["weight"] = weight
        width = getattr(os2, "usWidthClass", None)
        if type(width) is int and width in _WIDTHS:
            found["width"] = width
        selection = getattr(os2, "fsSelection", None)
        if type(selection) is int:
            found["italic"] = bool(selection & _FS_SELECTION_ITALIC)

    if "italic" not in found:
        head = font.get("head")
        style = getattr(head, "macStyle", None)
        if type(style) is int:
            found["italic"] = bool(style & _MAC_STYLE_ITALIC)
    return found


def _cmap(font) -> dict[int, str]:
    """Every character the font maps, to the glyph it draws it with.

    A symbol font (Webdings, say) carries only a symbol subtable, which
    ``getBestCmap`` does not consider, so every subtable is read then.
    """
    best = font.getBestCmap()
    if best:
        return dict(best)
    merged: dict[int, str] = {}
    table = font.get("cmap")
    for subtable in getattr(table, "tables", []):
        for code, name in (getattr(subtable, "cmap", None) or {}).items():
            merged.setdefault(code, name)
    return merged


def _kind(font, cmap: dict[int, str]) -> dict[str, Any]:
    """Whether the font draws emoji, in colour, and at which bitmap sizes.

    ``strikes`` are the pixel sizes a bitmap colour font opens at; a renderer
    has to draw it at one of them and scale.
    """
    found: dict[str, Any] = {"emoji": all(code in cmap for code in EMOJI_PROBES)}
    color = next((name for table, name in _COLOR_TABLES if table in font), None)
    if color:
        found["color"] = color
    strikes: set[int] = set()
    try:
        # sbix sizes come from bitmaps: fontTools would load every picture.
        if "CBLC" in font:
            strikes = {s.bitmapSizeTable.ppemY for s in font["CBLC"].strikes}
    except Exception:  # noqa: BLE001 - sizes unknown is not a failure
        strikes = set()
    if strikes:
        found["strikes"] = sorted(int(x) for x in strikes if x)
    return found


def _repertoire(font) -> tuple[list[list[Any]], int]:
    """The visible characters: ``[[text, glyph name, glyph id, name]]``.

    Capped at :data:`REPERTOIRE_LIMIT`; the second value is how many there are.
    """
    visible = sorted(
        (code, glyph) for code, glyph in _cmap(font).items()
        if unicodedata.category(chr(code)) not in _INVISIBLE)
    rows = []
    for code, glyph in visible[:REPERTOIRE_LIMIT]:
        try:
            glyph_id = font.getGlyphID(glyph)
        except Exception:  # noqa: BLE001 - a missing glyph still names its character
            glyph_id = None
        rows.append([chr(code), glyph, glyph_id, unicodedata.name(chr(code), "")])
    return rows, len(visible)


def sample_for(path: str, name: str) -> str:
    """What to draw for a font that cannot draw *name*, else ``""``.

    A symbol or emoji font has no letters, so its own name would be drawn as
    boxes. Characters it does have are picked evenly across its repertoire,
    preferring anything beyond ASCII, which is where such a font keeps them.
    """
    # Regional indicators are left out: two side by side would read as a flag.
    codes = [
        ord(text) for text, *_rest in read_metadata(path).get("repertoire", [])
        if len(text) == 1 and not 0x1F1E6 <= ord(text) <= 0x1F1FF
    ]
    if not codes:
        return ""
    have = set(codes)
    if all(ord(char) in have for char in name if not char.isspace()):
        return ""
    beyond = [code for code in codes if code > 0x7F]
    pool = beyond if len(beyond) >= SAMPLE_LENGTH else codes
    step = max(1, len(pool) // SAMPLE_LENGTH)
    return "".join(chr(code) for code in pool[::step][:SAMPLE_LENGTH])


def read_metadata(path: str) -> dict[str, Any]:
    """Everything *path* says about itself, or ``{}`` when it says nothing.

    A file this cannot parse is not an error: it still lists, it still draws,
    it simply has no facts to show. Results are kept until the file changes.
    """
    key = _cache_key(path)
    if key is not None and key in _cache:
        return _cache[key]

    found: dict[str, Any] = {}
    try:
        from fontTools.ttLib import TTFont  # noqa: PLC0415 - only needed here
        with TTFont(path, lazy=True, fontNumber=0) as font:
            found.update(_names(font))
            found.update(_shape(font))
            maxp = font.get("maxp")
            glyphs = getattr(maxp, "numGlyphs", None)
            if isinstance(glyphs, int) and glyphs > 0:
                found["glyphs"] = glyphs
            found.update(_kind(font, _cmap(font)))
            # A bitmap colour font is listed by its pictures, flags and
            # families included; the panel shows them as images.
            pictures = bitmap_font(path) if found.get("color") in ("sbix", "cbdt") else None
            if pictures is not None:
                found["images"] = True
                found["strikes"] = list(pictures.strikes)
                repertoire, count = pictures.rows(REPERTOIRE_LIMIT)
            else:
                repertoire, count = _repertoire(font)
        if count:
            found["repertoire"] = repertoire
            found["characters"] = count
    except Exception as err:  # noqa: BLE001 - an unreadable table is not a failure
        _LOGGER.debug("No metadata could be read from %s (%s)", path, err)
        found = {}

    if key is not None:
        if len(_cache) >= _CACHE_LIMIT:
            _cache.clear()
        _cache[key] = found
    return found


def font_kind(path: str) -> dict[str, Any]:
    """``emoji``, and ``color`` and ``strikes`` where there are any: what a
    consumer needs to offer a font for emoji, and to draw with it."""
    metadata = read_metadata(path)
    return {
        "emoji": bool(metadata.get("emoji")),
        **{field: metadata[field] for field in ("color", "strikes") if field in metadata},
    }


def font_shape(path: str) -> dict[str, Any]:
    """Just the weight, width and slant, for the stylesheet to declare."""
    metadata = read_metadata(path)
    return {
        field: metadata[field]
        for field in ("weight", "width", "italic")
        if field in metadata
    }


def width_percent(width: object) -> float | None:
    """``OS/2.usWidthClass`` as a CSS percentage, or ``None`` when it is normal."""
    percent = _WIDTHS.get(width) if type(width) is int else None
    return None if percent in (None, 100) else percent
