"""Config flow to add a vehicle and reconfigure one."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_ENGINE,
    CONF_FUEL_TYPE,
    CONF_NAME,
    CONF_ODOMETER,
    DOMAIN,
    FUEL_TYPES,
)
from .data import vehicle_settings

DEFAULT_FUEL_TYPE = FUEL_TYPES[0]

#: Vehicle settings that belong in the entry data; the name is the entry title.
#: Older installs may still carry values under these keys in ``entry.options``,
#: which would shadow the data through ``vehicle_settings()``; the reconfigure
#: step strips them.
_VEHICLE_KEYS = (CONF_FUEL_TYPE, CONF_ENGINE, CONF_ODOMETER)


def vehicle_schema() -> vol.Schema:
    """Return the shared add/reconfigure vehicle form.

    Values already known (reconfigure) are attached with
    ``FlowHandler.add_suggested_values_to_schema`` so the selector stays the
    direct schema value and the frontend can render it.
    """
    return vol.Schema(
        {
            vol.Required(CONF_NAME): TextSelector(),
            vol.Required(CONF_FUEL_TYPE, default=DEFAULT_FUEL_TYPE): SelectSelector(
                SelectSelectorConfig(
                    options=list(FUEL_TYPES),
                    translation_key=CONF_FUEL_TYPE,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_ENGINE): TextSelector(),
            vol.Optional(CONF_ODOMETER): NumberSelector(
                NumberSelectorConfig(min=0, step="any", unit_of_measurement="km")
            ),
        }
    )


def _name_taken(
    hass: HomeAssistant, name: str, exclude_entry_id: str | None = None
) -> bool:
    """Return True when another vehicle already uses this name."""
    needle = name.casefold()
    return any(
        entry.entry_id != exclude_entry_id and entry.title.casefold() == needle
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


def _vehicle_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Build entry data from the submitted wizard values.

    Cleared optional values are dropped instead of stored as ``""``; the name is
    always present and stripped.
    """
    data = {
        key: value
        for key, value in user_input.items()
        if value is not None and value != ""
    }
    data[CONF_NAME] = str(user_input.get(CONF_NAME, "")).strip()
    return data


class FuelUsageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a vehicle, or reconfigure an existing one in place."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the add vehicle form; the name is the entry title."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = str(user_input.get(CONF_NAME, "")).strip()
            if not name:
                errors[CONF_NAME] = "required"
            elif _name_taken(self.hass, name):
                return self.async_abort(reason="already_configured")
            else:
                return self.async_create_entry(
                    title=name, data=_vehicle_data(user_input)
                )

        return self.async_show_form(
            step_id="user", data_schema=vehicle_schema(), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfigure wizard: re-run setup for the same vehicle."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            name = str(user_input.get(CONF_NAME, "")).strip()
            if not name:
                errors[CONF_NAME] = "required"
            elif _name_taken(self.hass, name, entry.entry_id):
                errors[CONF_NAME] = "name_exists"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    title=name,
                    data=_vehicle_data(user_input),
                    options={
                        key: value
                        for key, value in entry.options.items()
                        if key not in _VEHICLE_KEYS
                    },
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vehicle_schema(), {**vehicle_settings(entry), CONF_NAME: entry.title}
            ),
            errors=errors,
        )
