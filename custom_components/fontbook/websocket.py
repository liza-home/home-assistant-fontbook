"""The WebSocket commands the panel and other frontends use.

Listing, reading one font's metadata, and deleting. Installing goes over HTTP,
because a font is too large for a WebSocket message.
"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .api import get_api
from .const import (
    DOMAIN,
    FRONTEND_URL_PATH,
    INTERFACE_SCALE_DEFAULT,
    PANEL_ELEMENT,
    PANEL_ICON,
    PANEL_LATEST,
    PANEL_TITLE,
    PANEL_URL_BASE,
    PICKER_ELEMENT,
)
from .fonts import list_installed, user_fonts_dir
from .storage import delete_fonts, refresh_revision, revision

_LOGGER = logging.getLogger(__name__)


async def _reply(hass: HomeAssistant) -> dict:
    """The installed fonts and the interface settings, read fresh."""
    fonts = await hass.async_add_executor_job(list_installed, hass)
    api = get_api(hass)
    return {
        "fonts": fonts,
        "revision": revision(),
        "interface_font": api.interface_font if api else None,
        "interface_scale": api.interface_scale if api else INTERFACE_SCALE_DEFAULT,
    }


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/info"})
@websocket_api.async_response
async def ws_info(hass: HomeAssistant, connection, msg: dict) -> None:
    """How another panel puts Fontbook on its own page.

    ``module_url`` is the current version's, ``latest_url`` the one that
    never changes. Set ``embedded`` on the panel element to show the library
    alone, sized by its host.
    """
    from .panel import panel_version  # noqa: PLC0415 - avoids a cycle at import

    version = await hass.async_add_executor_job(panel_version)
    connection.send_result(msg["id"], {
        "element": PANEL_ELEMENT,
        "module_url": f"{PANEL_URL_BASE}/{version}/{PANEL_ELEMENT}.js",
        "latest_url": f"{PANEL_URL_BASE}/{PANEL_LATEST}/{PANEL_ELEMENT}.js",
        "picker_element": PICKER_ELEMENT,
        "picker_url": f"{PANEL_URL_BASE}/{PANEL_LATEST}/{PICKER_ELEMENT}.js",
        "version": version,
        "url_path": FRONTEND_URL_PATH,
        "title": PANEL_TITLE,
        "icon": PANEL_ICON,
    })


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/list"})
@websocket_api.async_response
async def ws_list(hass: HomeAssistant, connection, msg: dict) -> None:
    """Every installed font, read fresh.

    Re-read on every call, so a font copied into the folder by hand shows up
    without a restart.
    """
    connection.send_result(msg["id"], await _reply(hass))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/set_interface_font",
    vol.Optional("font"): vol.Any(str, None),
})
@websocket_api.async_response
async def ws_set_interface_font(hass: HomeAssistant, connection, msg: dict) -> None:
    """Draw the whole interface in one font, or put it back to the default.

    An absent or null ``font`` is the way back: without it the user would have
    to edit the entry by hand to undo a font they do not like.
    """
    api = get_api(hass)
    if api is None:
        connection.send_error(msg["id"], "not_ready", "Fontbook is not set up")
        return

    wanted = msg.get("font") or None
    if wanted is not None:
        fonts = await hass.async_add_executor_job(list_installed, hass)
        if not any(font["id"] == wanted for font in fonts):
            connection.send_error(
                msg["id"], "unknown_font", f"No font is installed as {wanted}")
            return

    await api.async_set_interface_font(wanted)
    connection.send_result(msg["id"], await _reply(hass))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/set_interface_scale",
    vol.Optional("scale"): vol.Any(vol.Coerce(float), None),
})
@websocket_api.async_response
async def ws_set_interface_scale(hass: HomeAssistant, connection, msg: dict) -> None:
    """Size the interface's text, or put it back to Home Assistant's own size.

    Out-of-range values are clamped rather than refused, so a caller that asks
    for something unusable gets the nearest usable size instead of an error.
    """
    api = get_api(hass)
    if api is None:
        connection.send_error(msg["id"], "not_ready", "Fontbook is not set up")
        return

    wanted = msg.get("scale")
    await api.async_set_interface_scale(
        INTERFACE_SCALE_DEFAULT if wanted is None else wanted)
    connection.send_result(msg["id"], await _reply(hass))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/delete",
    vol.Required("fonts"): vol.All([str], vol.Length(min=1)),
})
@websocket_api.async_response
async def ws_delete(hass: HomeAssistant, connection, msg: dict) -> None:
    """Remove the named fonts and answer with what is left."""
    user_dir = user_fonts_dir(hass)
    try:
        removed = await hass.async_add_executor_job(
            delete_fonts, user_dir, list(msg["fonts"]))
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_font", str(err))
        return
    except OSError as err:
        _LOGGER.exception("Could not remove a font")
        connection.send_error(msg["id"], "delete_failed", str(err))
        return

    await hass.async_add_executor_job(refresh_revision, user_dir)

    # The interface cannot stay pointed at a font that is no longer installed,
    # so deleting the applied one puts the default back.
    api = get_api(hass)
    if api is not None and api.interface_font in removed:
        await api.async_set_interface_font(None)

    if removed and api:
        api.async_notify_changed()
    connection.send_result(msg["id"], {**await _reply(hass), "removed": removed})


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/metadata",
    vol.Required("font"): str,
})
@websocket_api.async_response
async def ws_metadata(hass: HomeAssistant, connection, msg: dict) -> None:
    """What one font says about itself.

    Asked for on its own rather than carried by the list: reading a font's
    name table is only wanted for the font being looked at, and the list is
    re-read on every change.
    """
    api = get_api(hass)
    if api is None:
        connection.send_error(msg["id"], "not_ready", "Fontbook is not set up")
        return

    found = await api.async_font_metadata(msg["font"])
    connection.send_result(msg["id"], {"font": msg["font"], "metadata": found})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@websocket_api.async_response
async def ws_subscribe(hass: HomeAssistant, connection, msg: dict) -> None:
    """Send the font list now, and again whenever the folder changes."""
    api = get_api(hass)
    if api is None:
        connection.send_error(msg["id"], "not_ready", "Fontbook is not set up")
        return

    @callback
    def changed() -> None:
        hass.async_create_task(_push(hass, connection, msg["id"]))

    connection.subscriptions[msg["id"]] = api.async_add_listener(changed)
    connection.send_result(msg["id"])
    await _push(hass, connection, msg["id"])


async def _push(hass: HomeAssistant, connection, subscription: int) -> None:
    connection.send_message(
        websocket_api.event_message(subscription, await _reply(hass)))


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    """Register the commands. Called once, from the integration's setup."""
    websocket_api.async_register_command(hass, ws_info)
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_delete)
    websocket_api.async_register_command(hass, ws_metadata)
    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_set_interface_font)
    websocket_api.async_register_command(hass, ws_set_interface_scale)
