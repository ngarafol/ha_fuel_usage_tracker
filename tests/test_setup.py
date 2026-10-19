"""Entry setup: one device, all 27 sensors, shared identity attributes."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.fuelusagetracker import const
from tests.helpers import DEFAULT_VEHICLE, SENSOR_KEYS, setup_vehicle

#: Rendered unit of every sensor key (docs/ARCHITECTURE.md sensor key table);
#: `None` means the sensor is unitless. Guards how units are derived.
SENSOR_UNITS = {
    const.SENSOR_ODOMETER: "km",
    const.SENSOR_KM_SINCE_LAST_FILL: "km",
    const.SENSOR_TOTAL_DISTANCE: "km",
    const.SENSOR_TOTAL_LITERS: "L",
    const.SENSOR_TOTAL_COST: "EUR",
    const.SENSOR_AVG_PRICE_PER_LITER: "EUR/L",
    const.SENSOR_LAST_FILL: None,
    const.SENSOR_LAST_FILL_COST: "EUR",
    const.SENSOR_LAST_FILL_LITERS: "L",
    const.SENSOR_LAST_PRICE_PER_LITER: "EUR/L",
    const.SENSOR_LAST_CONSUMPTION: "L/100km",
    const.SENSOR_AVG_CONSUMPTION: "L/100km",
    const.SENSOR_COST_PER_KM: "EUR/km",
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


async def test_setup_creates_all_twenty_seven_sensors(hass):
    entry = await setup_vehicle(hass)

    entities = _registered_entities(hass, entry)

    assert len(SENSOR_KEYS) == 27
    assert len(entities) == 27
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

    assert len({entity.unique_id for entity in entities}) == 27
    for entity in entities:
        key = hass.states.get(entity.entity_id).attributes["key"]
        assert entity.unique_id == f"{entry.entry_id}_{key}"
