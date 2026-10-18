"""Config flow to add a vehicle and options flow to edit one."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
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

#: Vehicle settings the options flow may write; the name is the entry title.
_EDITABLE_OPTION_KEYS = (CONF_FUEL_TYPE, CONF_ENGINE, CONF_ODOMETER)


def vehicle_schema() -> vol.Schema:
    """Return the shared add/edit vehicle form.

    Values already known (edit) are attached with
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


class FuelUsageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add one vehicle."""

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
                    title=name, data={**user_input, CONF_NAME: name}
                )

        return self.async_show_form(
            step_id="user", data_schema=vehicle_schema(), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the edit vehicle options flow.

        No delete step: removing a config entry is native to the Home Assistant
        UI and needs no destructive automation from this integration.
        """
        return FuelUsageOptionsFlow()


class FuelUsageOptionsFlow(OptionsFlow):
    """Edit one vehicle, prefilled with its merged settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the edit vehicle form."""
        entry = self.config_entry
        errors: dict[str, str] = {}

        if user_input is not None:
            name = str(user_input.pop(CONF_NAME, "")).strip()
            if not name:
                errors[CONF_NAME] = "required"
            elif _name_taken(self.hass, name, entry.entry_id):
                errors[CONF_NAME] = "name_exists"
            else:
                options = {**entry.options}
                for key in _EDITABLE_OPTION_KEYS:
                    if key in user_input:
                        options[key] = user_input[key]
                if name != entry.title:
                    self.hass.config_entries.async_update_entry(entry, title=name)
                return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vehicle_schema(), {**vehicle_settings(entry), CONF_NAME: entry.title}
            ),
            errors=errors,
        )
