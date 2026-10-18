"""Entry setup: one device, all 14 sensors, shared identity attributes."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.fuelusagetracker import const
from tests.helpers import DEFAULT_VEHICLE, SENSOR_KEYS, setup_vehicle


def _registered_entities(hass, entry):
    registry = er.async_get(hass)
    return er.async_entries_for_config_entry(registry, entry.entry_id)


async def test_setup_creates_the_vehicle_device(hass):
    entry = await setup_vehicle(hass)

    device = dr.async_get(hass).async_get_device({(const.DOMAIN, entry.entry_id)})

    assert device is not None
    assert device.name == f"{const.ENTITY_PREFIX} {entry.title}"


async def test_setup_creates_all_fourteen_sensors(hass):
    entry = await setup_vehicle(hass)

    entities = _registered_entities(hass, entry)

    assert len(SENSOR_KEYS) == 14
    assert len(entities) == 14
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
