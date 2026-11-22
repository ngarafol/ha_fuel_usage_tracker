"""Entry setup: one device, all 30 sensors, shared identity attributes."""

from __future__ import annotations

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.fuelusagetracker import const
from tests.helpers import (
    DEFAULT_VEHICLE,
    SENSOR_KEYS,
    make_entry,
    sensor_state,
    setup_vehicle,
)

#: A vehicle image the wizard would accept.
IMAGE = "/local/cars/passat.jpg"

#: Rendered unit of every sensor key (docs/ARCHITECTURE.md sensor key table);
#: `None` means the sensor is unitless. Guards how units are derived.
SENSOR_UNITS = {
    const.SENSOR_ODOMETER: "km",
    const.SENSOR_DISTANCE_TO_LAST_FILL: "km",
    const.SENSOR_RANGE_FULL_TANK: "km",
    const.SENSOR_TOTAL_DISTANCE: "km",
    const.SENSOR_TOTAL_LITERS: "L",
    const.SENSOR_CONSUMED_LITERS: "L",
    const.SENSOR_TOTAL_COST: "EUR",
    const.SENSOR_CONSUMED_COST: "EUR",
    const.SENSOR_AVG_PRICE_PER_LITER: "EUR/L",
    const.SENSOR_LAST_FILL: None,
    const.SENSOR_LAST_FILL_COST: "EUR",
    const.SENSOR_LAST_FILL_LITERS: "L",
    const.SENSOR_LAST_PRICE_PER_LITER: "EUR/L",
    const.SENSOR_LAST_CONSUMPTION: "L/100km",
    const.SENSOR_AVG_CONSUMPTION: "L/100km",
    const.SENSOR_COST_PER_100KM: "EUR/100km",
    const.SENSOR_FILL_COUNT: None,
    const.SENSOR_MONTH_DISTANCE: "km",
    const.SENSOR_MONTH_LITERS: "L",
    const.SENSOR_MONTH_COST: "EUR",
    const.SENSOR_MONTH_AVG_CONSUMPTION: "L/100km",
    const.SENSOR_MONTH_FILL_COUNT: None,
    const.SENSOR_ROLLING_DISTANCE: "km",
    const.SENSOR_ROLLING_LITERS: "L",
    const.SENSOR_ROLLING_COST: "EUR",
    const.SENSOR_ROLLING_AVG_CONSUMPTION: "L/100km",
    const.SENSOR_YEAR_DISTANCE: "km",
    const.SENSOR_YEAR_LITERS: "L",
    const.SENSOR_YEAR_COST: "EUR",
    const.SENSOR_YEAR_AVG_CONSUMPTION: "L/100km",
}


def _registered_entities(hass, entry):
    registry = er.async_get(hass)
    return er.async_entries_for_config_entry(registry, entry.entry_id)


async def test_setup_creates_the_vehicle_device(hass):
    entry = await setup_vehicle(hass)

    device = dr.async_get(hass).async_get_device({(const.DOMAIN, entry.entry_id)})

    assert device is not None
    assert device.name == f"{const.ENTITY_PREFIX} {entry.title}"


async def test_setup_creates_all_thirty_sensors(hass):
    entry = await setup_vehicle(hass)

    entities = _registered_entities(hass, entry)

    assert len(SENSOR_KEYS) == 30
    assert len(entities) == 30
    for entity in entities:
        assert entity.entity_id.startswith(f"sensor.{const.ENTITY_PREFIX}_")
    assert {
        hass.states.get(entity.entity_id).attributes["key"] for entity in entities
    } == set(SENSOR_KEYS)


async def test_every_sensor_carries_the_identity_attributes(hass):
    entry = await setup_vehicle(hass)

    for entity in _registered_entities(hass, entry):
        attributes = hass.states.get(entity.entity_id).attributes
        assert attributes["vehicle"] == entry.entry_id
        assert attributes["vehicle_name"] == entry.title
        assert attributes["fuel_type"] == DEFAULT_VEHICLE[const.CONF_FUEL_TYPE]
        assert attributes["engine"] == DEFAULT_VEHICLE[const.CONF_ENGINE]


async def test_every_sensor_carries_its_contracted_unit(hass):
    entry = await setup_vehicle(hass)

    units = {
        hass.states.get(entity.entity_id).attributes["key"]: entity.unit_of_measurement
        for entity in _registered_entities(hass, entry)
    }

    assert units == SENSOR_UNITS


async def test_every_sensor_carries_its_unique_id(hass):
    entry = await setup_vehicle(hass)

    entities = _registered_entities(hass, entry)

    assert len({entity.unique_id for entity in entities}) == 30
    for entity in entities:
        key = hass.states.get(entity.entity_id).attributes["key"]
        assert entity.unique_id == f"{entry.entry_id}_{key}"


async def test_distance_to_last_fill_replaced_km_since_last_fill(hass):
    entry = await setup_vehicle(hass)

    by_key = {
        hass.states.get(entity.entity_id).attributes["key"]: entity
        for entity in _registered_entities(hass, entry)
    }

    assert "km_since_last_fill" not in by_key
    distance = by_key[const.SENSOR_DISTANCE_TO_LAST_FILL]
    assert distance.unit_of_measurement == "km"
    assert distance.capabilities["state_class"] == "measurement"


async def test_consumed_sensors_carry_their_contracted_classes(hass):
    await setup_vehicle(hass)

    attributes = {
        state.attributes["key"]: state.attributes
        for state in hass.states.async_all("sensor")
    }

    liters = attributes[const.SENSOR_CONSUMED_LITERS]
    assert liters.get("device_class") is None
    assert liters["state_class"] == "total"

    cost = attributes[const.SENSOR_CONSUMED_COST]
    assert cost["device_class"] == "monetary"
    assert cost["state_class"] == "total"


async def test_per_100km_and_range_sensors_carry_their_contracted_classes(hass):
    await setup_vehicle(hass)

    attributes = {
        state.attributes["key"]: state.attributes
        for state in hass.states.async_all("sensor")
    }

    cost = attributes[const.SENSOR_COST_PER_100KM]
    assert cost.get("device_class") is None
    assert cost["state_class"] == "measurement"

    distance = attributes[const.SENSOR_RANGE_FULL_TANK]
    assert distance["device_class"] == "distance"
    assert distance["state_class"] == "measurement"


async def test_sensors_expose_the_configured_vehicle_image(hass):
    await setup_vehicle(hass, make_entry(**{const.CONF_IMAGE: IMAGE}))

    attributes = sensor_state(hass, const.SENSOR_FILL_COUNT).attributes

    assert attributes["entity_picture"] == IMAGE


@pytest.mark.parametrize("image", [None, "", "   "])
async def test_an_absent_or_blank_image_exposes_no_entity_picture(hass, image):
    await setup_vehicle(hass, make_entry(**{const.CONF_IMAGE: image}))

    assert "entity_picture" not in sensor_state(hass, const.SENSOR_FILL_COUNT).attributes


async def test_an_odd_image_value_does_not_break_the_sensor(hass):
    await setup_vehicle(hass, make_entry(**{const.CONF_IMAGE: 42}))

    state = sensor_state(hass, const.SENSOR_FILL_COUNT)

    assert state.state == "0"
    assert state.attributes.get("entity_picture") in (None, "42")
