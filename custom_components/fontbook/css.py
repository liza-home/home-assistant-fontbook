"""The stylesheet that makes installed fonts real to the browser.

Two jobs in one document. Every installed font becomes an ``@font-face``, so a
theme or a card can name it; and, when one has been chosen, the properties Home
Assistant draws its interface with are pointed at it, so the whole frontend is
drawn in it.

Each face is declared twice: under the font's own family, which is the name a
user expects to write, and under ``fonts-manager-<id>``, which is stable even
when two foundries ship a family under the same name.
"""
from __future__ import annotations

from urllib.parse import quote

from .const import (
    FONT_FILE_URL,
    FONTS_CSS_URL,
    INTERFACE_FONT_FALLBACK,
    INTERFACE_FONT_PROPERTIES,
    INTERFACE_SCALE_DEFAULT,
    INTERFACE_SCALE_MAX,
    INTERFACE_SCALE_MIN,
    INTERFACE_SCALE_PROPERTY,
)
from .metadata import width_percent

#: What a browser is told to expect, by extension. ``.ttc`` is absent: a
#: collection is not something a browser will load as a web font.
_CSS_FORMATS = {
    ".ttf": "truetype",
    ".otf": "opentype",
    ".woff": "woff",
    ".woff2": "woff2",
}

#: Read off the style name, since that is all a font without a usable ``OS/2``
#: table offers. Ordered longest-first, so "extrabold" is not matched as "bold".
_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("extralight", 200),
    ("ultralight", 200),
    ("extrabold", 800),
    ("ultrabold", 800),
    ("semibold", 600),
    ("demibold", 600),
    ("thin", 100),
    ("light", 300),
    ("medium", 500),
    ("regular", 400),
    ("normal", 400),
    ("book", 400),
    ("black", 900),
    ("heavy", 900),
    ("bold", 700),
)

_ITALIC = ("italic", "oblique")


def font_weight(style: str) -> int:
    """The numeric weight *style* names, or 400 when it names none."""
    squashed = "".join(str(style).lower().split())
    for name, weight in _WEIGHTS:
        if name in squashed:
            return weight
    return 400


def font_style(style: str) -> str:
    """``"italic"`` when *style* says so, else ``"normal"``."""
    squashed = "".join(str(style).lower().split())
    return "italic" if any(name in squashed for name in _ITALIC) else "normal"


def declared_weight(font: dict) -> int:
    """The weight a font is declared at, preferring what the file itself says.

    A style name is a label, not a value: a face called "Text" or "Semi" names
    a weight no list of substrings can be made to cover. The ``OS/2`` table
    carries the number, so it wins wherever the font bothered to write one.
    """
    weight = font.get("weight")
    if type(weight) is int and 1 <= weight <= 1000:
        return weight
    return font_weight(font.get("style", ""))


def declared_style(font: dict) -> str:
    """Whether a font is declared italic, preferring what the file itself says."""
    italic = font.get("italic")
    if isinstance(italic, bool):
        return "italic" if italic else "normal"
    return font_style(font.get("style", ""))


def _encode(value: str) -> str:
    """*value* with everything outside ``A-Za-z0-9_`` as its UTF-8 bytes in hex.

    Mirrored by ``previewFamily`` in ``fonts-manager-preview.js``; the two must
    agree exactly.
    """
    out: list[str] = []
    for char in str(value):
        if char.isascii() and (char.isalnum() or char == "_"):
            out.append(char)
        else:
            out.extend(f"-{byte:02x}" for byte in char.encode("utf-8"))
    return "".join(out)


def alias_family(font_id: str) -> str:
    """The stable family name one font file is always available under.

    Two ids can never land on one family, which the font's own family name
    cannot promise: two foundries may ship a family under the same name.
    """
    return "fonts-manager-" + _encode(font_id)


def family_alias(family: str) -> str:
    """The stable name every face of one family is available under.

    What :func:`alias_family` is for a file, this is for a family. Applying a
    font to the interface has to name all of its weights, or the browser draws
    a bold heading by smearing the regular face rather than by using the bold
    one sitting right beside it.
    """
    return "fonts-manager-family-" + _encode(family)


def css_string(value: str) -> str:
    """*value* as a quoted CSS string, with what would end it escaped."""
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def font_file_url(font_id: str, revision: str | None = None) -> str:
    """The address of one font file, carrying *revision* so a replaced font is refetched."""
    url = FONT_FILE_URL.format(font_id=quote(str(font_id), safe=""))
    return f"{url}?r={quote(str(revision), safe='')}" if revision else url


def _face(family: str, font: dict, revision: str | None) -> str:
    url = font_file_url(font["id"], revision)
    fmt = _CSS_FORMATS.get(str(font.get("ext", "")).lower())
    src = f'url({css_string(url)})' + (f" format({css_string(fmt)})" if fmt else "")
    stretch = width_percent(font.get("width"))
    return (
        "@font-face {\n"
        f"  font-family: {css_string(family)};\n"
        f"  src: {src};\n"
        f"  font-weight: {declared_weight(font)};\n"
        f"  font-style: {declared_style(font)};\n"
        + (f"  font-stretch: {stretch:g}%;\n" if stretch else "")
        + "  font-display: swap;\n"
        "}"
    )


def _servable(font: dict) -> bool:
    """Whether a browser can use this font at all.

    A ``.ttc`` collection cannot be loaded as a web font, so it is left out
    rather than declared and silently never drawn.
    """
    return str(font.get("ext", "")).lower() in _CSS_FORMATS


def interface_font_block(family: str | None) -> str:
    """The rule that points Home Assistant's typography at *family*.

    Empty for ``None``, which is how the interface goes back to the font Home
    Assistant ships with: a declaration that is never written cannot be one the
    user has to undo.
    """
    if not family:
        return ""
    value = f"{css_string(family)}, {INTERFACE_FONT_FALLBACK}"
    lines = "\n".join(f"  {prop}: {value};" for prop in INTERFACE_FONT_PROPERTIES)
    return f"html {{\n{lines}\n}}"


def clamp_interface_scale(value: object) -> float:
    """*value* as a usable scale, falling back to the default.

    Anything unreadable, and anything outside the range the panel offers,
    becomes something safe: a hand-edited entry should not be able to leave the
    interface at a size nothing can undo.
    """
    try:
        scale = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return INTERFACE_SCALE_DEFAULT
    if scale != scale:  # NaN, which compares false against every bound
        return INTERFACE_SCALE_DEFAULT
    return min(max(scale, INTERFACE_SCALE_MIN), INTERFACE_SCALE_MAX)


def interface_scale_block(scale: object) -> str:
    """The rule that sizes Home Assistant's typography.

    Empty at the default, for the same reason the font rule is: a declaration
    that is never written cannot be one the user has to undo.
    """
    value = clamp_interface_scale(scale)
    if value == INTERFACE_SCALE_DEFAULT:
        return ""
    return f"html {{\n  {INTERFACE_SCALE_PROPERTY}: {value:g};\n}}"


def _interface_faces(fonts: list[dict], interface_font: str | None) -> list[dict]:
    """The faces the interface should be drawn with, for *interface_font*.

    Every servable font of the chosen font's family and source, so the browser
    has a real bold to reach for. Empty when the chosen font is not installed.
    """
    chosen = next(
        (f for f in fonts if f.get("id") == interface_font and _servable(f)), None)
    if chosen is None:
        return []
    family = (chosen.get("family") or "").strip()
    if not family:
        return [chosen]
    return [
        font for font in fonts
        if _servable(font)
        and (font.get("family") or "").strip() == family
        and font.get("source") == chosen.get("source")
    ]


def build_stylesheet(
    fonts: list[dict],
    revision: str | None = None,
    interface_font: str | None = None,
    interface_scale: object = None,
) -> str:
    """The whole stylesheet: every usable font, then the interface rule."""
    blocks: list[str] = [
        "/* Generated by Fontbook. Do not edit: it is rebuilt on every request. */"
    ]

    for font in fonts:
        if not font.get("id") or not _servable(font):
            continue
        families = [alias_family(font["id"])]
        if family := (font.get("family") or "").strip():
            families.insert(0, family)
        blocks.extend(_face(name, font, revision) for name in families)

    interface_family: str | None = None
    if interface_font:
        faces = _interface_faces(fonts, interface_font)
        if faces:
            # Only the applied family is given an alias of its own: declaring
            # every family twice over would double the stylesheet to no end.
            family = (faces[0].get("family") or "").strip()
            interface_family = (
                family_alias(family) if family else alias_family(interface_font))
            blocks.extend(_face(interface_family, font, revision) for font in faces)
        else:
            # The chosen font is not readable, or not servable. Its own alias
            # still applies, rather than leaving the interface silently unchanged.
            interface_family = alias_family(interface_font)

    if block := interface_font_block(interface_family):
        blocks.append(block)
    if block := interface_scale_block(interface_scale):
        blocks.append(block)

    return "\n\n".join(blocks) + "\n"


def stylesheet_url(revision: str | None = None) -> str:
    """The address of the generated stylesheet, keyed by *revision*."""
    if not revision:
        return FONTS_CSS_URL
    return f"{FONTS_CSS_URL}?r={quote(str(revision), safe='')}"


__all__ = [
    "alias_family",
    "build_stylesheet",
    "clamp_interface_scale",
    "declared_style",
    "declared_weight",
    "family_alias",
    "font_style",
    "font_weight",
    "interface_font_block",
    "interface_scale_block",
    "stylesheet_url",
]
