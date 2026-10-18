"""Config flow and options flow checks (docs/ARCHITECTURE.md)."""

from __future__ import annotations

from homeassistant.data_entry_flow import FlowResultType

from custom_components.fuelusagetracker import const
from tests.helpers import DEFAULT_VEHICLE, make_entry


async def test_user_flow_creates_entry_titled_with_vehicle_name(hass):
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DEFAULT_VEHICLE
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_VEHICLE[const.CONF_NAME]
    entry = result["result"]
    assert entry.data[const.CONF_NAME] == DEFAULT_VEHICLE[const.CONF_NAME]
    assert entry.data[const.CONF_FUEL_TYPE] == DEFAULT_VEHICLE[const.CONF_FUEL_TYPE]
    assert entry.data[const.CONF_ENGINE] == DEFAULT_VEHICLE[const.CONF_ENGINE]
    assert float(entry.data[const.CONF_ODOMETER]) == DEFAULT_VEHICLE[const.CONF_ODOMETER]


async def test_user_flow_duplicate_name_aborts(hass):
    first = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": "user"}
    )
    await hass.config_entries.flow.async_configure(first["flow_id"], DEFAULT_VEHICLE)
    await hass.async_block_till_done()

    second = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": "user"}
    )
    if second["type"] is FlowResultType.FORM:
        second = await hass.config_entries.flow.async_configure(
            second["flow_id"], DEFAULT_VEHICLE
        )

    assert second["type"] is FlowResultType.ABORT


async def test_options_flow_updates_settings(hass):
    entry = make_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            const.CONF_NAME: entry.title,
            const.CONF_FUEL_TYPE: "petrol",
            const.CONF_ENGINE: "2.0 TDI",
            const.CONF_ODOMETER: 12000.0,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[const.CONF_ENGINE] == "2.0 TDI"
    assert float(entry.options[const.CONF_ODOMETER]) == 12000.0
    assert entry.options[const.CONF_FUEL_TYPE] == "petrol"
    assert entry.title == DEFAULT_VEHICLE[const.CONF_NAME]


async def test_options_flow_name_change_updates_entry_title(hass):
    entry = make_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**DEFAULT_VEHICLE, const.CONF_NAME: "Ranger"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.title == "Ranger"
