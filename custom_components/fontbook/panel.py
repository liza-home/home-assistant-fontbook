"""The sidebar panel's registration and the route its modules are served from.

The version lives in the *path* rather than a ``?v=`` query string because the
panel has no build step: its modules import each other with plain relative
specifiers, which the browser resolves against the importing module's URL.
Versioning the directory therefore busts the whole module graph at once;
versioning only the entry point would leave the browser free to satisfy those
relative imports from cache and produce a mixed old/new graph.
"""
from __future__ import annotations

import logging
import os

from aiohttp import web

from homeassistant.components.frontend import async_remove_panel
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    FRONTEND_URL_PATH,
    PANEL_ELEMENT,
    PANEL_ICON,
    PANEL_LATEST,
    PANEL_TITLE,
    PANEL_URL_BASE,
)

_LOGGER = logging.getLogger(__name__)

PANEL_DIR = os.path.join(os.path.dirname(__file__), "panel")


def panel_version() -> str:
    """A version string taken from the newest module in the panel directory.

    So it only moves when a file actually changes, and always moves when one
    does -- otherwise the browser keeps serving the previous bundle from cache.
    Walks the tree, because the stylesheet is split across ``panel/styles/``.

    Touches the disk, so callers inside the event loop hand it to an executor.
    """
    try:
        newest = max(
            os.path.getmtime(os.path.join(dirpath, name))
            for dirpath, _dirnames, filenames in os.walk(PANEL_DIR)
            for name in filenames
            if name.endswith(".js")
        )
    except (OSError, ValueError):
        return "0"
    return str(int(newest))


class PanelAssetView(HomeAssistantView):
    """Serve the panel's JS modules under a version-prefixed URL.

    The path may name a module in a subdirectory (``styles/base.js``), so the
    route takes a multi-segment match, pinned to ``.js`` in the pattern itself.

    ``latest`` stands in for the version a consuming integration cannot know,
    and is the one spelling served without caching.
    """

    url = PANEL_URL_BASE + r"/{version}/{filename:.+\.js}"
    name = "fontbook:panel"
    requires_auth = False  # panel modules are fetched by the browser without a token

    async def get(
        self, request: web.Request, version: str, filename: str,
    ) -> web.StreamResponse:
        """Return one panel asset, or 404 for anything outside the panel dir."""
        # Resolved whole and required to still sit under the panel directory:
        # realpath first, so neither ".." nor a symlink out of the tree can be
        # used to climb out of it.
        if os.path.isabs(filename) or os.path.splitdrive(filename)[0]:
            return web.Response(status=404)
        path = os.path.realpath(os.path.join(PANEL_DIR, filename))
        root = os.path.realpath(PANEL_DIR)
        if os.path.commonpath([path, root]) != root or not os.path.isfile(path):
            return web.Response(status=404)

        # A real version expires the file by changing the path, so that one may
        # be held forever. "latest" never changes, so it must never be kept.
        cache = (
            "no-cache"
            if version == PANEL_LATEST
            else "public, max-age=31536000, immutable"
        )
        return web.FileResponse(
            path,
            headers={
                "Content-Type": "application/javascript; charset=utf-8",
                "Cache-Control": cache,
            },
        )


def async_register_view(hass: HomeAssistant) -> None:
    """Register the route the panel's modules are served from.

    Separate from :func:`async_register`, because a view cannot be registered
    twice and the panel is registered again on every reload.
    """
    hass.http.register_view(PanelAssetView)


async def async_register(hass: HomeAssistant) -> None:
    """Put Fontbook in the sidebar; each user can hide it there."""
    version = await hass.async_add_executor_job(panel_version)
    await async_register_panel(
        hass,
        frontend_url_path=FRONTEND_URL_PATH,
        webcomponent_name=PANEL_ELEMENT,
        module_url=f"{PANEL_URL_BASE}/{version}/{PANEL_ELEMENT}.js",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=True,
        config={"version": version},
    )


def async_unregister(hass: HomeAssistant) -> None:
    """Take Fontbook out of the sidebar again."""
    try:
        async_remove_panel(hass, FRONTEND_URL_PATH)
    except Exception:  # noqa: BLE001 - an unload must not fail over the sidebar
        _LOGGER.debug("The %s panel was already gone", DOMAIN)
