"""Adding Fontbook from the user interface.

There is nothing to configure: one instance owns one font folder, so the flow
only confirms and creates the entry. The manifest's ``single_config_entry``
is what keeps it to one.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class FontsManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """A single-instance flow with nothing to ask."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Confirm, then create the one entry this integration has."""
        if user_input is None:
            return self.async_show_form(step_id="user")
        return self.async_create_entry(title="Fontbook", data={})
