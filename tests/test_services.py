"""Service checks: add_fillup statistics, delete_fillup, input validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError

from custom_components.fuelusagetracker import const
from custom_components.fuelusagetracker.data import FillUp
from tests.helpers import (
    BASE_ODOMETER,
    FILLUP_DATE_1,
    FILLUP_DATE_2,
    FILLUP_DATE_MID,
    add_fillup,
    call_service,
    sensor_state,
    sensor_value,
    setup_vehicle,
    two_full_fillups,
)

VALIDATION_ERRORS = (vol.Invalid, HomeAssistantError)


async def test_add_fillup_computes_statistics(hass):
    entry = await setup_vehicle(hass)

    await two_full_fillups(hass, entry.entry_id)

    assert sensor_value(hass, const.SENSOR_TOTAL_COST) == 127.5
    assert sensor_value(hass, const.SENSOR_TOTAL_LITERS) == 85.0
    assert sensor_value(hass, const.SENSOR_AVG_CONSUMPTION) == 9.0
    assert sensor_value(hass, const.SENSOR_LAST_CONSUMPTION) == 9.0
    assert sensor_value(hass, const.SENSOR_TOTAL_DISTANCE) == 500.0
    assert sensor_value(hass, const.SENSOR_KM_SINCE_LAST_FILL) == 0.0


async def test_partial_fill_is_folded_into_the_leg(hass):
    entry = await setup_vehicle(hass)

    await add_fillup(
        hass, entry.entry_id, 40, 60.0, odometer=BASE_ODOMETER, date=FILLUP_DATE_1
    )
    await add_fillup(
        hass,
        entry.entry_id,
        10,
        15.0,
        odometer=BASE_ODOMETER + 250,
        full=False,
        date=FILLUP_DATE_MID,
    )
    await add_fillup(
        hass, entry.entry_id, 45, 67.5, odometer=BASE_ODOMETER + 500, date=FILLUP_DATE_2
    )

    assert sensor_value(hass, const.SENSOR_TOTAL_LITERS) == 95.0
    assert sensor_value(hass, const.SENSOR_TOTAL_DISTANCE) == 500.0
    # The partial fill's litres are part of the leg ending at the second full
    # fill-up: 10 L + 45 L over 500 km.
    assert sensor_value(hass, const.SENSOR_AVG_CONSUMPTION) == 11.0
    assert sensor_value(hass, const.SENSOR_LAST_CONSUMPTION) == 11.0


async def test_consumption_is_unknown_when_no_leg_can_be_measured(hass):
    entry = await setup_vehicle(hass)

    await add_fillup(
        hass, entry.entry_id, 40, 60.0, odometer=BASE_ODOMETER, date=FILLUP_DATE_1
    )
    # A full tank without an odometer closes nothing: no leg is measurable.
    await add_fillup(hass, entry.entry_id, 30, 45.0, date=FILLUP_DATE_2)

    assert sensor_state(hass, const.SENSOR_LAST_CONSUMPTION).state == "unknown"
    assert sensor_state(hass, const.SENSOR_AVG_CONSUMPTION).state == "unknown"


async def test_delete_fillup_removes_data_and_updates_sensors(hass):
    entry = await setup_vehicle(hass)
    await two_full_fillups(hass, entry.entry_id)

    fillup_id = sensor_state(hass, const.SENSOR_LAST_FILL).attributes["fillup_id"]
    await call_service(
        hass,
        const.SERVICE_DELETE_FILLUP,
        {const.CONF_VEHICLE: entry.entry_id, const.CONF_FILLUP_ID: fillup_id},
    )

    assert sensor_value(hass, const.SENSOR_FILL_COUNT) == 1
    assert sensor_value(hass, const.SENSOR_TOTAL_LITERS) == 40.0


async def test_delete_unknown_fillup_id_raises(hass):
    entry = await setup_vehicle(hass)

    with pytest.raises(HomeAssistantError):
        await call_service(
            hass,
            const.SERVICE_DELETE_FILLUP,
            {const.CONF_VEHICLE: entry.entry_id, const.CONF_FILLUP_ID: "no-such-id"},
        )


async def test_unknown_vehicle_raises(hass):
    await setup_vehicle(hass)

    with pytest.raises(HomeAssistantError):
        await call_service(
            hass,
            const.SERVICE_ADD_FILLUP,
            {const.CONF_VEHICLE: "Ghost", const.CONF_LITERS: 10, const.CONF_PRICE: 10},
        )


async def test_zero_liters_is_rejected_by_the_schema(hass):
    entry = await setup_vehicle(hass)

    with pytest.raises(VALIDATION_ERRORS):
        await call_service(
            hass,
            const.SERVICE_ADD_FILLUP,
            {const.CONF_VEHICLE: entry.entry_id, const.CONF_LITERS: 0, const.CONF_PRICE: 10},
        )


async def test_negative_price_is_rejected_by_the_schema(hass):
    entry = await setup_vehicle(hass)

    with pytest.raises(VALIDATION_ERRORS):
        await call_service(
            hass,
            const.SERVICE_ADD_FILLUP,
            {
                const.CONF_VEHICLE: entry.entry_id,
                const.CONF_LITERS: 10,
                const.CONF_PRICE: -1,
            },
        )


async def test_last_fill_sensor_exposes_the_fillup_history(hass):
    """The card reads its history from these attributes, not from entity ids."""
    entry = await setup_vehicle(hass)

    await add_fillup(
        hass,
        entry.entry_id,
        40,
        60.0,
        odometer=BASE_ODOMETER,
        station="Shell",
        notes="oldest",
        date=FILLUP_DATE_1,
    )
    await add_fillup(
        hass,
        entry.entry_id,
        20,
        25.0,
        odometer=BASE_ODOMETER + 250,
        full=False,
        station="OMV",
        date=FILLUP_DATE_MID,
    )
    await add_fillup(
        hass,
        entry.entry_id,
        45,
        67.5,
        odometer=BASE_ODOMETER + 500,
        station="INA",
        notes="newest",
        date=FILLUP_DATE_2,
    )

    attributes = sensor_state(hass, const.SENSOR_LAST_FILL).attributes
    history = attributes["fillups"]

    # The flattened attributes describe the newest fill-up.
    assert attributes["fillup_id"] == history[0]["id"]
    assert attributes["liters"] == 45.0
    assert attributes["price"] == 67.5
    assert attributes["price_per_liter"] == 1.5
    assert attributes["odometer"] == BASE_ODOMETER + 500
    assert attributes["station"] == "INA"
    assert attributes["full"] is True
    assert attributes["notes"] == "newest"

    # The history is the plain FillUp.as_dict() shape, newest first.
    assert isinstance(history, list)
    assert all(isinstance(item, dict) for item in history)
    assert set(history[0]) == set(
        FillUp(
            id="id", date=datetime(2026, 1, 1, tzinfo=UTC), liters=1.0, price=1.0
        ).as_dict()
    )
    assert [item["liters"] for item in history] == [45.0, 20.0, 40.0]
    assert [item["station"] for item in history] == ["INA", "OMV", "Shell"]
    assert history[0]["full"] is True
    assert history[1]["full"] is False
    assert history[0]["notes"] == "newest"
    assert history[-1]["notes"] == "oldest"


async def test_last_fill_history_is_capped_at_the_fifty_newest(hass):
    entry = await setup_vehicle(hass)
    coordinator = entry.runtime_data
    start = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    for index in range(55):
        await coordinator.async_add_fillup(
            FillUp(
                id=f"fill-{index}",
                date=start + timedelta(hours=index),
                liters=float(index + 1),
                price=10.0 + index,
                odometer=BASE_ODOMETER + index * 10,
            )
        )
    await hass.async_block_till_done()

    history = sensor_state(hass, const.SENSOR_LAST_FILL).attributes["fillups"]

    assert sensor_value(hass, const.SENSOR_FILL_COUNT) == 55.0
    assert len(history) == 50
    # Indices 54 down to 5: the 50 newest, oldest of the 55 dropped.
    assert [item["id"] for item in history] == [
        f"fill-{index}" for index in range(54, 4, -1)
    ]
