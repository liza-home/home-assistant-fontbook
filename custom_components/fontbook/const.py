"""Names and limits the rest of Fontbook agrees on."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "fontbook"

#: Below Home Assistant's configuration directory. ``www`` is the folder Home
#: Assistant already serves at ``/local``, so a font put here is reachable by
#: anything that wants it by URL, and is kept by backups and core updates.
USER_FONTS_SUBDIR: Final = ("www", "fonts")

#: What Pillow can draw with directly.
FONT_EXTENSIONS: Final = (".ttf", ".otf", ".ttc")

#: What a browser can use but Pillow cannot read, so it is decoded first.
WEBFONT_EXTENSIONS: Final = (".woff", ".woff2")

#: A whole family arrives as one of these, which is how a foundry hands it out.
ARCHIVE_EXTENSIONS: Final = (".zip",)

#: Where decoded web fonts go. Kept out of the font folder itself: that folder
#: is the user's own, and is served publicly.
CACHE_DIRNAME: Final = ".webfont-cache"
CACHE_SUBDIR: Final = (DOMAIN, CACHE_DIRNAME)

#: Enough for a colour emoji font, whose bitmaps run to a hundred megabytes.
#: Uploads stream to disk, so this bounds the disk, not memory.
MAX_FONT_BYTES: Final = 256 * 1024 * 1024

#: A whole family's archive or collection, which is several fonts rather than one.
MAX_ARCHIVE_BYTES: Final = 256 * 1024 * 1024

#: Past this an archive is refused outright rather than unpacked member by member.
MAX_ARCHIVE_MEMBERS: Final = 200

URL_BASE: Final = f"/api/{DOMAIN}"
FONT_UPLOAD_URL: Final = f"{URL_BASE}/font"
FONT_FILE_URL: Final = URL_BASE + "/font_file/{font_id}"
FONT_SAMPLE_URL: Final = URL_BASE + "/sample/{font_id}"
FONT_GLYPH_URL: Final = URL_BASE + "/glyph/{font_id}/{key}"
FONTS_CSS_URL: Final = f"{URL_BASE}/fonts.css"

PANEL_URL_BASE: Final = f"/{DOMAIN}_panel"

#: The version segment a consumer uses when it cannot know the current one.
#: Served without caching, since the name never changes but the file does.
PANEL_LATEST: Final = "latest"

#: The custom elements other panels may put on their own pages.
PANEL_ELEMENT: Final = "fonts-manager-panel"
PICKER_ELEMENT: Final = "fonts-manager-picker"

#: Fired on Home Assistant's bus whenever a font is installed or removed,
#: with the new ``revision``: for a consumer's backend, which no WebSocket
#: subscription reaches.
EVENT_FONTS_CHANGED: Final = f"{DOMAIN}_fonts_changed"

PANEL_TITLE: Final = "Fontbook"
PANEL_ICON: Final = "mdi:format-font"
FRONTEND_URL_PATH: Final = DOMAIN

#: The module Home Assistant loads on every page, which puts the generated
#: stylesheet in the document. Unversioned, since it is registered once.
FRONTEND_MODULE_URL: Final = f"{PANEL_URL_BASE}/{PANEL_LATEST}/fonts-manager-frontend.js"

#: The entry option holding the font the whole interface is drawn in.
CONF_INTERFACE_FONT: Final = "interface_font"

#: The entry option holding how large the interface's text is drawn.
CONF_INTERFACE_SCALE: Final = "interface_scale"


#: The variable every ``--ha-font-size-*`` token is derived from. The frontend
#: declares it and leaves it at 1; nothing in Home Assistant offers a way to
#: change it, which is the gap this fills.
INTERFACE_SCALE_PROPERTY: Final = "--ha-font-size-scale"

#: Bounded deliberately. A scale large enough to push the panel off the screen
#: would take with it the control needed to undo it.
INTERFACE_SCALE_DEFAULT: Final = 1.0
INTERFACE_SCALE_MIN: Final = 0.8
INTERFACE_SCALE_MAX: Final = 2.0

#: The properties Home Assistant draws its interface with. ``--ha-font-family-code``
#: is absent on purpose: code and entity ids stay monospaced. The older spellings
#: are kept because corners of the interface still read them.
INTERFACE_FONT_PROPERTIES: Final = (
    "--ha-font-family-body",
    "--ha-font-family-heading",
    "--ha-font-family-longform",
    "--primary-font-family",
    "--mdc-typography-font-family",
    "--mdc-typography-body1-font-family",
    "--mdc-typography-body2-font-family",
    "--mdc-typography-button-font-family",
    "--mdc-typography-caption-font-family",
    "--mdc-typography-headline6-font-family",
    "--mdc-typography-subtitle1-font-family",
    "--mdc-typography-subtitle2-font-family",
    "--paper-font-common-base_-_font-family",
    "--paper-font-body1_-_font-family",
    "--paper-font-subhead_-_font-family",
    "--paper-font-headline_-_font-family",
    "--paper-font-title_-_font-family",
    "--paper-font-caption_-_font-family",
)

#: What follows the chosen font, for a character it does not carry. Spelled out
#: rather than referring to the property being set: a custom property whose
#: value reads itself is a cycle, which CSS throws away whole.
INTERFACE_FONT_FALLBACK: Final = "Roboto, Noto, sans-serif"

#: What a sample image may be asked for, so a query cannot ask for a poster.
SAMPLE_MIN_SIZE: Final = 8
SAMPLE_MAX_SIZE: Final = 160
SAMPLE_MAX_CHARS: Final = 120
SAMPLE_MAX_WIDTH: Final = 2000
#: The sample is one line, so this only has to survive a font with absurd
#: metrics. The endpoint needs no token, so nothing here may be unbounded.
SAMPLE_MAX_HEIGHT: Final = 400
DEFAULT_SAMPLE_SIZE: Final = 48
DEFAULT_SAMPLE_TEXT: Final = "The quick brown fox jumps over the lazy dog"
