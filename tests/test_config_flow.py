"""Config flow checks: the add wizard and the reconfigure wizard.

Contract: docs/ARCHITECTURE.md. Reconfigure replaces the old options flow: it
writes ``entry.data``, updates the title, clears the vehicle keys from
``entry.options`` and reloads the entry.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fuelusagetracker import config_flow, const
from tests.helpers import DEFAULT_VEHICLE, make_entry, sensor_state, setup_vehicle

VEHICLE_KEYS = (const.CONF_FUEL_TYPE, const.CONF_ENGINE, const.CONF_ODOMETER)

#: What the old Configure form left behind: values that used to shadow entry.data.
STALE_OPTIONS = {
    const.CONF_FUEL_TYPE: "lpg",
    const.CONF_ENGINE: "Stale 1.0",
    const.CONF_ODOMETER: 99999.0,
}


def _suggested(result: dict) -> dict:
    """The form's suggested values, as attached to the schema markers."""
    return {
        marker.schema: marker.description["suggested_value"]
        for marker in result["data_schema"].schema
        if isinstance(marker, vol.Marker) and marker.description
    }


async def _reconfigure_form(hass, entry):
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM
    return result


async def _submit(hass, result, user_input: dict) -> dict:
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


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


async def test_reconfigure_form_is_prefilled_with_the_current_settings(hass):
    entry = await setup_vehicle(hass)

    result = await _reconfigure_form(hass, entry)

    assert result["step_id"] == "reconfigure"
    assert _suggested(result) == {
        const.CONF_NAME: entry.title,
        const.CONF_FUEL_TYPE: DEFAULT_VEHICLE[const.CONF_FUEL_TYPE],
        const.CONF_ENGINE: DEFAULT_VEHICLE[const.CONF_ENGINE],
        const.CONF_ODOMETER: DEFAULT_VEHICLE[const.CONF_ODOMETER],
    }


async def test_reconfigure_updates_data_title_and_reloads(hass):
    entry = await setup_vehicle(hass)
    before = entry.runtime_data

    result = await _reconfigure_form(hass, entry)
    result = await _submit(
        hass,
        result,
        {
            const.CONF_NAME: "Ranger",
            const.CONF_FUEL_TYPE: "petrol",
            const.CONF_ENGINE: "2.0 TDI",
            const.CONF_ODOMETER: 12000.0,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert entry.title == "Ranger"
    assert entry.data[const.CONF_NAME] == "Ranger"
    assert entry.data[const.CONF_FUEL_TYPE] == "petrol"
    assert entry.data[const.CONF_ENGINE] == "2.0 TDI"
    assert float(entry.data[const.CONF_ODOMETER]) == 12000.0
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not before

    attributes = sensor_state(hass, const.SENSOR_FILL_COUNT).attributes
    assert attributes["engine"] == "2.0 TDI"
    assert attributes["fuel_type"] == "petrol"


async def test_reconfigure_replaces_a_stale_option_value(hass):
    """The old Configure form wrote options that shadowed entry.data."""
    entry = await setup_vehicle(
        hass,
        MockConfigEntry(
            domain=const.DOMAIN,
            title=DEFAULT_VEHICLE[const.CONF_NAME],
            data=dict(DEFAULT_VEHICLE),
            options=dict(STALE_OPTIONS),
        ),
    )

    # The stale option is winning before the fix is exercised.
    assert (
        sensor_state(hass, const.SENSOR_FILL_COUNT).attributes["engine"]
        == STALE_OPTIONS[const.CONF_ENGINE]
    )

    result = await _reconfigure_form(hass, entry)
    result = await _submit(
        hass,
        result,
        {
            const.CONF_NAME: entry.title,
            const.CONF_FUEL_TYPE: "petrol",
            const.CONF_ENGINE: "2.0 TDI",
            const.CONF_ODOMETER: 12000.0,
        },
    )

    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert entry.data[const.CONF_ENGINE] == "2.0 TDI"
    assert entry.data[const.CONF_FUEL_TYPE] == "petrol"
    for key in VEHICLE_KEYS:
        assert key not in entry.options
    assert (
        sensor_state(hass, const.SENSOR_FILL_COUNT).attributes["engine"] == "2.0 TDI"
    )


async def test_reconfigure_rejects_a_blank_name(hass):
    entry = await setup_vehicle(hass)

    result = await _reconfigure_form(hass, entry)
    result = await _submit(
        hass, result, {**DEFAULT_VEHICLE, const.CONF_NAME: "   "}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {const.CONF_NAME: "required"}
    assert entry.title == DEFAULT_VEHICLE[const.CONF_NAME]


async def test_reconfigure_rejects_another_vehicles_name(hass):
    entry = await setup_vehicle(hass)
    other = await setup_vehicle(hass, make_entry(**{const.CONF_NAME: "Ranger"}))

    result = await _reconfigure_form(hass, entry)
    result = await _submit(
        hass, result, {**DEFAULT_VEHICLE, const.CONF_NAME: "Ranger"}
    )

    assert result["errors"] == {const.CONF_NAME: "name_exists"}
    assert entry.title == DEFAULT_VEHICLE[const.CONF_NAME]
    assert other.title == "Ranger"
    assert other.data[const.CONF_NAME] == "Ranger"
    assert other.data[const.CONF_ENGINE] == DEFAULT_VEHICLE[const.CONF_ENGINE]


async def test_reconfigure_accepts_its_own_name(hass):
    entry = await setup_vehicle(hass)

    result = await _reconfigure_form(hass, entry)
    result = await _submit(
        hass, result, {**DEFAULT_VEHICLE, const.CONF_NAME: entry.title}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.title == DEFAULT_VEHICLE[const.CONF_NAME]


async def test_reconfigure_clears_a_cleared_optional_field(hass):
    entry = await setup_vehicle(hass)

    result = await _reconfigure_form(hass, entry)
    result = await _submit(
        hass,
        result,
        {
            const.CONF_NAME: entry.title,
            const.CONF_FUEL_TYPE: DEFAULT_VEHICLE[const.CONF_FUEL_TYPE],
            const.CONF_ENGINE: "",
        },
    )

    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert const.CONF_ENGINE not in entry.data
    assert const.CONF_ODOMETER not in entry.data
    assert sensor_state(hass, const.SENSOR_FILL_COUNT).attributes["engine"] is None


async def test_reconfigure_replaces_the_options_flow(hass):
    entry = await setup_vehicle(hass)

    assert hasattr(config_flow.FuelUsageConfigFlow, "async_step_reconfigure")
    assert config_flow.FuelUsageConfigFlow.async_supports_options_flow(entry) is False
    assert not hasattr(config_flow, "FuelUsageOptionsFlow")
