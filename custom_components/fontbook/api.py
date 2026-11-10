"""The object another integration reaches Fontbook through.

Placed in ``hass.data[DOMAIN]`` at setup, so a consumer does nothing more than::

    fonts = hass.data["fontbook"]
    path = await fonts.async_resolve_path("inter-bold")

Every method that touches the disk has an ``async_`` form that hands the work
to an executor; the plain forms are there for code already running in one.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant, callback

from . import fonts as fonts_mod
from . import metadata as metadata_mod
from . import storage as storage_mod
from .const import (
    EVENT_FONTS_CHANGED,
    CONF_INTERFACE_FONT,
    CONF_INTERFACE_SCALE,
    DOMAIN,
    INTERFACE_SCALE_DEFAULT,
)
from .css import clamp_interface_scale

_LOGGER = logging.getLogger(__name__)


class FontsManagerAPI:
    """What Fontbook offers other integrations.

    Nothing here knows about any particular consumer: a caller hands over font
    ids and gets back names and file paths.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._listeners: list[Callable[[], None]] = []
        self.entry: Any = None

    @property
    def interface_font(self) -> str | None:
        """The font the whole interface is drawn in, or ``None`` for the default."""
        if self.entry is None:
            return None
        return self.entry.options.get(CONF_INTERFACE_FONT) or None

    async def async_set_interface_font(self, font_id: str | None) -> None:
        """Draw the interface in *font_id*, or in Home Assistant's own font for ``None``.

        Stored on the entry, so the choice survives a restart without this
        integration owning a second place where state is kept.
        """
        if self.entry is None:
            raise RuntimeError("Fontbook has no config entry")
        options = {**self.entry.options, CONF_INTERFACE_FONT: font_id or None}
        self._hass.config_entries.async_update_entry(self.entry, options=options)
        self.async_notify_changed()

    @property
    def interface_scale(self) -> float:
        """How large the interface's text is drawn, as a multiplier of 1."""
        if self.entry is None:
            return INTERFACE_SCALE_DEFAULT
        return clamp_interface_scale(
            self.entry.options.get(CONF_INTERFACE_SCALE, INTERFACE_SCALE_DEFAULT))

    async def async_set_interface_scale(self, scale: object) -> None:
        """Draw the interface's text at *scale*, clamped to what the panel offers."""
        if self.entry is None:
            raise RuntimeError("Fontbook has no config entry")
        value = clamp_interface_scale(scale)
        options = {**self.entry.options, CONF_INTERFACE_SCALE: value}
        self._hass.config_entries.async_update_entry(self.entry, options=options)
        self.async_notify_changed()

    @property
    def fonts_dir(self) -> str:
        """The directory the user's fonts live in."""
        return fonts_mod.user_fonts_dir(self._hass)

    def list_fonts(self) -> list[dict[str, str]]:
        """Every installed font. Blocking; prefer :meth:`async_list_fonts`."""
        return fonts_mod.list_installed(self._hass)

    async def async_list_fonts(self) -> list[dict[str, str]]:
        """Every installed font, as ``{"id", "name", "family", "style", "ext", "size", "source"}``."""
        return await self._hass.async_add_executor_job(
            fonts_mod.list_installed, self._hass)

    def resolve_path(self, font_id: str | None) -> str | None:
        """The file a font id names. Blocking; prefer :meth:`async_resolve_path`."""
        return fonts_mod.resolve_installed(self._hass, font_id)

    async def async_resolve_path(self, font_id: str | None) -> str | None:
        """The file a font id names, ready to hand to Pillow, or ``None``."""
        return await self._hass.async_add_executor_job(
            fonts_mod.resolve_installed, self._hass, font_id)

    def font_metadata(self, font_id: str | None) -> dict[str, Any]:
        """What a font says about itself. Blocking; prefer the async form."""
        path = self.resolve_path(font_id)
        return metadata_mod.read_metadata(path) if path else {}

    async def async_font_metadata(self, font_id: str | None) -> dict[str, Any]:
        """What a font says about itself: its names, its weight, its licence.

        ``{}`` when no font answers to *font_id*, and when the file carries
        nothing worth reading -- neither is an error.
        """
        return await self._hass.async_add_executor_job(self.font_metadata, font_id)

    def revision(self) -> str:
        """A digest of the font folder, so a cache keyed by font id can expire.

        A replaced font keeps its id, so the id alone is not enough to tell a
        consumer that what it cached is no longer what the id means.
        """
        return storage_mod.revision()

    async def async_refresh_revision(self) -> str:
        """Re-read the font folder and return its digest."""
        return await self._hass.async_add_executor_job(
            storage_mod.refresh_revision, self.fonts_dir)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call *listener* whenever a font is installed or removed.

        Returns the function that unsubscribes it again.
        """
        self._listeners.append(listener)

        @callback
        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    @callback
    def async_notify_changed(self) -> None:
        """Tell every listener the font folder changed, and the bus too. One
        failing is its own."""
        bus = getattr(self._hass, "bus", None)
        if bus is not None:
            bus.async_fire(EVENT_FONTS_CHANGED, {"revision": storage_mod.revision()})
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:  # noqa: BLE001 - a consumer must not break the rest
                _LOGGER.exception("A fonts listener raised")


@callback
def get_api(hass: HomeAssistant) -> FontsManagerAPI | None:
    """The API object, or ``None`` when Fontbook is not set up."""
    data: Any = hass.data.get(DOMAIN)
    return data if isinstance(data, FontsManagerAPI) else None
