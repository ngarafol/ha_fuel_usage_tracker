"""Persistence: the fill-ups must survive a config entry reload."""

from __future__ import annotations

from custom_components.fuelusagetracker import const
from tests.helpers import sensor_value, setup_vehicle, two_full_fillups


async def test_fillups_survive_an_entry_reload(hass):
    entry = await setup_vehicle(hass)
    await two_full_fillups(hass, entry.entry_id)
    assert sensor_value(hass, const.SENSOR_FILL_COUNT) == 2

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert sensor_value(hass, const.SENSOR_FILL_COUNT) == 2
    assert sensor_value(hass, const.SENSOR_TOTAL_LITERS) == 85.0
    assert sensor_value(hass, const.SENSOR_LAST_CONSUMPTION) == 9.0
