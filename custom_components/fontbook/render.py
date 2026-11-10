"""Drawing a sample of a font, the way a consumer would draw with it.

The browser previews a font with ``FontFace``, which proves it loads. This
proves something different: that Pillow -- which is what an integration
rendering images actually uses -- can draw with the file. A font that previews
in the panel but cannot be drawn here would fail only in the consumer.
"""
from __future__ import annotations

import io
import logging

from PIL import Image, ImageDraw, ImageFont

from .const import (
    SAMPLE_MAX_CHARS,
    SAMPLE_MAX_HEIGHT,
    SAMPLE_MAX_SIZE,
    SAMPLE_MAX_WIDTH,
    SAMPLE_MIN_SIZE,
)

_LOGGER = logging.getLogger(__name__)

_PADDING = 8


def clamp_size(value) -> int:
    """*value* as a usable point size, whatever the query carried."""
    try:
        size = int(value)
    except (TypeError, ValueError):
        return SAMPLE_MIN_SIZE
    return max(SAMPLE_MIN_SIZE, min(SAMPLE_MAX_SIZE, size))


def parse_color(value) -> tuple[int, int, int, int]:
    """A ``#rrggbb`` or ``#rrggbbaa`` string as RGBA, defaulting to black."""
    text = str(value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) not in (6, 8):
        return (0, 0, 0, 255)
    try:
        channels = [int(text[i:i + 2], 16) for i in range(0, len(text), 2)]
    except ValueError:
        return (0, 0, 0, 255)
    while len(channels) < 4:
        channels.append(255)
    return tuple(channels[:4])  # type: ignore[return-value]


def _load(path: str, size: int) -> ImageFont.FreeTypeFont:
    """The font at *path*, falling back to the one size a bitmap font has."""
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        # A colour-emoji font carries a single strike and refuses every other
        # size; its own size is the only one it will open at.
        for strike in (109, 128, 160):
            try:
                return ImageFont.truetype(path, strike)
            except OSError:
                continue
        raise


def sample_text(value) -> str:
    """*value* as the single line this endpoint promises to draw.

    Newlines would otherwise be measured and drawn as separate lines, and the
    view needs no token, so a tall image is memory anyone could ask for.
    """
    return " ".join(str(value or "").split())[:SAMPLE_MAX_CHARS]


def render_sample(
    path: str,
    text: str,
    size: int,
    color: tuple[int, int, int, int],
) -> bytes:
    """A transparent PNG of *text* drawn in the font at *path*."""
    sample = sample_text(text)
    font = _load(path, clamp_size(size))

    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    left, top, right, bottom = measure.textbbox((0, 0), sample, font=font)
    width = min(SAMPLE_MAX_WIDTH, max(1, right - left) + _PADDING * 2)
    height = min(SAMPLE_MAX_HEIGHT, max(1, bottom - top) + _PADDING * 2)

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    try:
        draw.text((_PADDING - left, _PADDING - top), sample, font=font, fill=color)
    except OSError:
        # An embedded-colour font is drawn in its own colours, not ours.
        draw.text((_PADDING - left, _PADDING - top), sample, font=font,
                  embedded_color=True)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
