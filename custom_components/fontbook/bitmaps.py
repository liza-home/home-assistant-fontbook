"""Pictures of the glyphs in a bitmap colour font, read straight from the file.

A colour emoji font keeps a picture per glyph -- Apple's in an ``sbix`` table,
Google's in ``CBDT`` -- and many of those glyphs are reached by no single
character: a flag is two regional indicators the font joins into one, a family
a run of people joined by zero-width joiners. A browser draws them only where
it understands the format, and a list of characters cannot reach them at all,
so the panel shows the glyphs themselves, from the pictures stored here.

Apple Color Emoji is close to 200 MB, nearly all of it pictures, so ``sbix`` is
read by hand: its index is a list of offsets, which gives one glyph's picture
without loading the rest. ``CBDT`` fonts are an order of magnitude smaller and
are read through fontTools. Every read blocks on the disk.
"""
from __future__ import annotations

import io
import logging
import os
import re
import struct
import threading
import unicodedata
from typing import Any

_LOGGER = logging.getLogger(__name__)

#: The strike pictures are taken from: the size closest to this. Apple's
#: largest is 160 px, which stays sharp in the panel's largest view.
PREFERRED_PPEM = 160

#: ``sbix`` graphic types holding a picture a browser can show.
_PICTURE_TYPES = {b"png ", b"jpg ", b"tiff"}

#: Apple's glyph names spell what a glyph stands for: ``u1F1E6_u1F1F9`` is a
#: flag, ``u1F9D6.1.M`` a person with skin tone 1 and the male sign,
#: ``u1F3C3.0.M.u27A1`` a man running towards the right.
_APPLE_NAME = re.compile(r"^(u[0-9A-F]{4,6}(?:_u[0-9A-F]{4,6})*)((?:\.[0-9A-Za-z]+)*)$")

_ZWJ, _VS16 = 0x200D, 0xFE0F
_SKIN_TONES = {str(n): 0x1F3FA + n for n in range(1, 6)}  # 1 -> U+1F3FB ... 5 -> U+1F3FF
_GENDERS = {"M": 0x2642, "W": 0x2640}

_lock = threading.Lock()
_cache: dict[tuple[str, int, int], "_BitmapFont | None"] = {}


def _key(path: str) -> tuple[str, int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return path, stat.st_mtime_ns, stat.st_size


def bitmap_font(path: str) -> "_BitmapFont | None":
    """The pictures in the font at *path*, or ``None`` when it has none."""
    key = _key(path)
    if key is None:
        return None
    with _lock:
        if key in _cache:
            return _cache[key]
    try:
        found = _BitmapFont.open(path)
    except Exception as err:  # noqa: BLE001 - an unreadable table means no pictures
        _LOGGER.debug("No glyph pictures could be read from %s (%s)", path, err)
        found = None
    with _lock:
        # Two or three emoji fonts at most; their indexes are all that is kept.
        if len(_cache) >= 8:
            _cache.clear()
        _cache[key] = found
    return found


def glyph_png(path: str, key: str) -> bytes | None:
    """One glyph's picture.

    *key* is a glyph id, or ``u`` and the hex code points of the text it draws,
    joined by ``-``: ``u1F1E6-1F1F9`` is the Austrian flag.
    """
    font = bitmap_font(path)
    if font is None:
        return None
    if key.isdigit():
        return font.picture(int(key))
    if key[:1] in "uU" and re.fullmatch(r"[0-9A-Fa-f]{1,6}(-[0-9A-Fa-f]{1,6})*", key[1:]):
        text = "".join(chr(int(part, 16)) for part in key[1:].split("-"))
        gid = font.glyph_for(text)
        return font.picture(gid) if gid is not None else None
    return None


def _plain(text: str) -> str:
    """*text* without variation selector 16, which a keyboard may or may not add."""
    return text.replace(chr(_VS16), "")


def _joined_plainly(code: int) -> bool:
    """A part written straight after the one before, not through a joiner."""
    return (
        0x1F1E6 <= code <= 0x1F1FF      # regional indicators: flags
        or 0xE0020 <= code <= 0xE007F   # tag characters: subdivision flags
        or code == 0x20E3               # combining keycap
    )


def _text_of_apple_name(name: str) -> str:
    """What an Apple glyph name stands for, or ``""`` when it is not understood.

    The parts before the first dot are the emoji themselves, joined by zero
    width joiners unless they are a flag or a keycap. After it come a skin tone
    per person (``0`` for none), the gender, and a direction to face.
    """
    match = _APPLE_NAME.match(name)
    if not match:
        return ""
    people = [[int(part[1:], 16)] for part in match.group(1).split("_")]
    tail: list[int] = []
    for part in match.group(2).split(".")[1:]:
        if part.isdigit() and all(digit in "012345" for digit in part):
            # One tone for a lone person, or one each for the first and last.
            targets = [people[0]] if len(part) == 1 else [people[0], people[-1]]
            if len(part) > 2:
                return ""
            for target, digit in zip(targets, part):
                if digit != "0":
                    target.append(_SKIN_TONES[digit])
        elif part in _GENDERS:
            tail += [_ZWJ, _GENDERS[part], _VS16]
        elif re.fullmatch(r"u[0-9A-F]{4,6}", part):
            tail += [_ZWJ, int(part[1:], 16), _VS16]
        else:
            # A variant this does not know how to spell: better no text than
            # the wrong emoji on someone's clipboard.
            return ""
    codes: list[int] = []
    for person in people:
        if codes and not _joined_plainly(person[0]):
            codes.append(_ZWJ)
        codes += person
    return "".join(chr(code) for code in codes + tail)


def _describe(text: str) -> str:
    """A name for *text*: the character's own, or a flag's, or its parts'."""
    if len(text) == 1:
        return unicodedata.name(text, "")
    codes = [ord(char) for char in text]
    if len(codes) == 2 and all(0x1F1E6 <= code <= 0x1F1FF for code in codes):
        return "FLAG " + "".join(chr(code - 0x1F1E6 + ord("A")) for code in codes)
    parts = [unicodedata.name(char, "") for char in text if ord(char) not in (_ZWJ, _VS16)]
    return " + ".join(part for part in parts if part)


def _mirror(data: bytes) -> bytes | None:
    """*data*, a picture, turned left to right, as a PNG."""
    from PIL import Image, ImageOps  # noqa: PLC0415 - only for a turned glyph

    try:
        with Image.open(io.BytesIO(data)) as image:
            out = io.BytesIO()
            ImageOps.mirror(image).save(out, "PNG")
    except OSError:
        return None
    return out.getvalue()


class _BitmapFont:
    """One bitmap colour font's glyph pictures, by glyph id."""

    def __init__(self, path: str, glyph_order: list[str], cmap: dict[int, str]) -> None:
        self.path = path
        self.glyph_order = glyph_order
        self.glyph_ids = {name: gid for gid, name in enumerate(glyph_order)}
        self.cmap = cmap
        self.kind = ""
        self.strikes: list[int] = []
        # sbix: where each glyph's record starts and ends, in the file.
        self._spans: list[tuple[int, int]] = []
        # CBDT: the pictures themselves, read once.
        self._pictures: dict[int, bytes] = {}
        self._ligatures: dict[str, list[str]] = {}
        self._by_text: dict[str, int] | None = None

    @classmethod
    def open(cls, path: str) -> "_BitmapFont | None":
        from fontTools.ttLib import TTFont  # noqa: PLC0415 - only needed here

        with TTFont(path, lazy=True, fontNumber=0) as font:
            if "sbix" not in font and "CBDT" not in font:
                return None
            best = font.getBestCmap() or {}
            found = cls(path, font.getGlyphOrder(), dict(best))
            if "sbix" in font:
                entry = font.reader.tables["sbix"]
                found._read_sbix(entry.offset, len(found.glyph_order))
            else:
                found._read_cbdt(font)
            if "GSUB" in font:
                found._read_ligatures(font)
        return found

    def _read_sbix(self, table: int, glyphs: int) -> None:
        self.kind = "sbix"
        with open(self.path, "rb") as handle:
            handle.seek(table)
            _version, _flags, count = struct.unpack(">HHI", handle.read(8))
            offsets = struct.unpack(f">{count}I", handle.read(4 * count))
            sizes = []
            for offset in offsets:
                handle.seek(table + offset)
                ppem, _ppi = struct.unpack(">HH", handle.read(4))
                sizes.append((ppem, offset))
            self.strikes = sorted(ppem for ppem, _offset in sizes)
            ppem, offset = min(sizes, key=lambda size: abs(size[0] - PREFERRED_PPEM))
            strike = table + offset
            handle.seek(strike + 4)
            starts = struct.unpack(f">{glyphs + 1}I", handle.read(4 * (glyphs + 1)))
        self._spans = [(strike + starts[gid], strike + starts[gid + 1]) for gid in range(glyphs)]

    def _read_cbdt(self, font) -> None:
        self.kind = "cbdt"
        cblc, cbdt = font["CBLC"], font["CBDT"]
        self.strikes = sorted(int(s.bitmapSizeTable.ppemY) for s in cblc.strikes)
        index = max(range(len(cblc.strikes)), key=lambda i: (
            -abs(cblc.strikes[i].bitmapSizeTable.ppemY - PREFERRED_PPEM)))
        for name, glyph in cbdt.strikeData[index].items():
            glyph.ensureDecompiled()
            data = getattr(glyph, "imageData", None)
            if data and name in self.glyph_ids:
                self._pictures[self.glyph_ids[name]] = bytes(data)

    def _read_ligatures(self, font) -> None:
        """Which glyphs each ligature glyph is made of: how Noto spells its flags."""
        try:
            lookups = font["GSUB"].table.LookupList.Lookup
        except AttributeError:
            return
        for lookup in lookups:
            for table in lookup.SubTable:
                inner = getattr(table, "ExtSubTable", table)
                for first, ligatures in (getattr(inner, "ligatures", None) or {}).items():
                    for ligature in ligatures:
                        self._ligatures.setdefault(
                            ligature.LigGlyph, [first, *ligature.Component])

    def picture(self, gid: int) -> bytes | None:
        """The picture glyph *gid* is drawn with, or ``None``."""
        if self.kind == "cbdt":
            return self._pictures.get(gid)
        mirrored = False
        for _ in range(4):  # 'dupe' and 'flip' point at another glyph, never far
            if not 0 <= gid < len(self._spans):
                return None
            start, end = self._spans[gid]
            if end - start <= 8:
                return None
            with open(self.path, "rb") as handle:
                handle.seek(start + 4)
                kind = handle.read(4)
                data = handle.read(end - start - 8)
            if kind in _PICTURE_TYPES:
                return _mirror(data) if mirrored else data
            if kind in (b"dupe", b"flip") and len(data) >= 2:
                # 'flip' is the other glyph facing the other way.
                mirrored ^= kind == b"flip"
                gid = struct.unpack(">H", data[:2])[0]
                continue
            return None
        return None

    def glyph_for(self, text: str) -> int | None:
        """The glyph drawing *text*, or ``None``."""
        if len(text) == 1 and (glyph := self.cmap.get(ord(text))) in self.glyph_ids:
            return self.glyph_ids[glyph]
        if self._by_text is None:
            self._by_text = {
                _plain(spelled): self.glyph_ids[glyph]
                for glyph, spelled in self.texts().items() if glyph in self.glyph_ids
            }
        return self._by_text.get(_plain(text))

    def has_picture(self, gid: int) -> bool:
        if self.kind == "cbdt":
            return gid in self._pictures
        start, end = self._spans[gid]
        return end - start > 8

    def texts(self) -> dict[str, str]:
        """What each glyph stands for, where that can be told."""
        found = {glyph: chr(code) for code, glyph in sorted(self.cmap.items(), reverse=True)}
        # A ligature is spelled by its parts, which may themselves be ligatures.
        for _ in range(4):
            changed = False
            for ligature, parts in self._ligatures.items():
                if ligature in found:
                    continue
                spelled = [found.get(part) for part in parts]
                if all(spelled):
                    found[ligature] = "".join(spelled)
                    changed = True
            if not changed:
                break
        for name in self.glyph_order:
            if name not in found and (text := _text_of_apple_name(name)):
                found[name] = text
        return found

    def rows(self, limit: int) -> tuple[list[list[Any]], int]:
        """``[[text, glyph name, glyph id, name]]`` for every glyph with a picture."""
        texts = self.texts()
        rows = []
        for gid, glyph in enumerate(self.glyph_order):
            if glyph.startswith(".") or not self.has_picture(gid):
                continue
            text = texts.get(glyph, "")
            rows.append([text, glyph, gid, _describe(text) if text else ""])
        return rows[:limit], len(rows)
