"""Fontbook: upload, preview and manage fonts for Home Assistant.

An integration that owns font storage and offers it to anything else running in
the same Home Assistant -- see ``api.FontsManagerAPI`` for what a consumer gets.
"""
from __future__ import annotations

import logging
import os

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import panel as panel_mod
from .api import FontsManagerAPI
from .const import DOMAIN, FRONTEND_MODULE_URL
from .fonts import user_fonts_dir
from .http import async_register_views
from .storage import refresh_revision, split_installed_collections, sweep_staging
from .websocket import async_register_commands

_LOGGER = logging.getLogger(__name__)



async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Tell the panel, and anything else listening, that the choice changed."""
    api: FontsManagerAPI | None = hass.data.get(DOMAIN)
    if api is not None:
        api.entry = entry
        api.async_notify_changed()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the font folder, the API, the views and the panel."""
    api = FontsManagerAPI(hass)
    api.entry = entry
    hass.data[DOMAIN] = api

    user_dir = user_fonts_dir(hass)
    await hass.async_add_executor_job(os.makedirs, user_dir, 0o755, True)
    await hass.async_add_executor_job(sweep_staging, user_dir)
    split = await hass.async_add_executor_job(split_installed_collections, user_dir)
    if split:
        _LOGGER.info("Split font collections into their fonts: %s", ", ".join(split))
    await hass.async_add_executor_job(refresh_revision, user_dir)

    # The views and commands are the http component's, not the entry's: they
    # cannot be registered twice, and a reload would do exactly that.
    if not hass.data.get(f"{DOMAIN}_views"):
        async_register_views(hass)
        panel_mod.async_register_view(hass)
        async_register_commands(hass)
        # Loaded on every page, which is what lets an uploaded font be used in
        # a theme or a card rather than only inside this integration's panel.
        add_extra_js_url(hass, FRONTEND_MODULE_URL)
        hass.data[f"{DOMAIN}_views"] = True

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await panel_mod.async_register(hass)
    _LOGGER.debug("Fontbook is serving fonts from %s", user_dir)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Take the panel down. The views stay, since they cannot be removed."""
    panel_mod.async_unregister(hass)
    hass.data.pop(DOMAIN, None)
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device,
) -> bool:
    """Let any device be deleted: Fontbook has none, so one is a leftover."""
    return True
