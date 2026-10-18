"""Monthly statistics: purchased litres vs. closed legs, local-time bucketing,
ordering, the history cap and the five ``month_*`` sensors.

Contract: ``docs/ARCHITECTURE.md`` "Period statistics" plus the 27-row sensor
key table.
"""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.helpers import entity_registry as er

from custom_components.fuelusagetracker import const
from custom_components.fuelusagetracker.data import FuelUsage, PeriodUsage
from tests.helpers import (
    BASE_ODOMETER,
    PERIOD_KEYS,
    SENSOR_KEYS,
    add_fillup,
    fill,
    sensor_state,
    sensor_value,
    setup_vehicle,
)

JANUARY = datetime(2026, 1, 10, 9, 0, tzinfo=UTC)
FEBRUARY = datetime(2026, 2, 10, 9, 0, tzinfo=UTC)

MONTH_KEYS = (
    const.SENSOR_MONTH_DISTANCE,
    const.SENSOR_MONTH_LITERS,
    const.SENSOR_MONTH_COST,
    const.SENSOR_MONTH_AVG_CONSUMPTION,
    const.SENSOR_MONTH_FILL_COUNT,
)


def month(usage: FuelUsage, key: str) -> PeriodUsage:
    """The one month bucket with the given ``YYYY-MM`` key."""
    months = {item.key: item for item in usage.months()}
    assert key in months, f"no bucket for {key}, got {sorted(months)}"
    return months[key]


def test_same_month_aggregates_purchases_and_the_closed_leg(utc_timezone):
    """40 L full, 30 L partial, 35 L full in one month: one 65 L / 800 km leg."""
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0, date=JANUARY, fillup_id="f0"),
            fill(30, 10400.0, full=False, date=JANUARY, fillup_id="f1"),
            fill(35, 10800.0, date=JANUARY, fillup_id="f2"),
        ]
    )

    january = month(usage, "2026-01")

    # Purchased that month: all three fill-ups.
    assert january.liters == 105.0
    assert january.cost == 157.5
    assert january.fill_count == 3
    # Closed leg: the partial fill's litres plus the closing full fill-up.
    assert january.distance == 800.0
    assert january.leg_liters == 65.0
    assert january.avg_consumption == 8.12


def test_partial_fill_counts_towards_its_own_month_but_consumes_in_the_closing_month(
    utc_timezone,
):
    """The 30 L bought in January closes a February leg."""
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0, date=JANUARY, fillup_id="f0"),
            fill(30, 10400.0, full=False, date=JANUARY, fillup_id="f1"),
            fill(35, 10800.0, date=FEBRUARY, fillup_id="f2"),
        ]
    )

    january = month(usage, "2026-01")
    february = month(usage, "2026-02")

    assert january.liters == 70.0
    assert january.cost == 105.0
    assert january.fill_count == 2
    assert january.leg_liters == 0.0
    assert january.distance is None
    assert january.avg_consumption is None

    assert february.liters == 35.0
    assert february.cost == 52.5
    assert february.fill_count == 1
    assert february.leg_liters == 65.0
    assert february.distance == 800.0
    assert february.avg_consumption == 8.12


def test_month_bucketing_uses_local_time(zagreb_timezone):
    """23:30 UTC on 31 January is already February in a UTC+1 zone."""
    usage = FuelUsage(
        fillups=[
            fill(
                40,
                10000.0,
                date=datetime(2026, 1, 31, 23, 30, tzinfo=UTC),
                fillup_id="f0",
            )
        ]
    )

    assert [item.key for item in usage.months()] == ["2026-02"]


def test_month_bucketing_stays_in_january_under_utc(utc_timezone):
    usage = FuelUsage(
        fillups=[
            fill(
                40,
                10000.0,
                date=datetime(2026, 1, 31, 23, 30, tzinfo=UTC),
                fillup_id="f0",
            )
        ]
    )

    assert [item.key for item in usage.months()] == ["2026-01"]


def test_months_without_fillups_are_omitted_not_zeroed(utc_timezone):
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0, date=JANUARY, fillup_id="f0"),
            fill(
                45,
                10500.0,
                date=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
                fillup_id="f1",
            ),
        ]
    )

    # February has no fill-up at all: omitted, never a zero row.
    assert [item.key for item in usage.months()] == ["2026-03", "2026-01"]


def test_months_are_newest_first(utc_timezone):
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0, date=JANUARY, fillup_id="f0"),
            fill(
                40,
                10500.0,
                date=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
                fillup_id="f1",
            ),
            fill(40, 10250.0, date=FEBRUARY, fillup_id="f2"),
        ]
    )

    assert [item.key for item in usage.months()] == [
        "2026-03",
        "2026-02",
        "2026-01",
    ]


async def test_month_cost_history_shape_order_and_cap(hass, utc_timezone):
    """30 months in, 24 newest-first dicts out, in the `as_dict()` shape."""
    entry = await setup_vehicle(hass)
    coordinator = entry.runtime_data
    dates = [
        datetime(2024 + index // 12, index % 12 + 1, 15, 12, 0, tzinfo=UTC)
        for index in range(30)
    ]

    for index, when in enumerate(dates):
        await coordinator.async_add_fillup(
            fill(
                40.0 + index,
                BASE_ODOMETER + index * 100,
                date=when,
                fillup_id=f"fill-{index}",
            )
        )
    await hass.async_block_till_done()

    history = sensor_state(hass, const.SENSOR_MONTH_COST).attributes["months"]

    expected = [f"{when.year:04d}-{when.month:02d}" for when in reversed(dates)]
    assert len(history) == const.MONTH_HISTORY_MONTHS == 24
    assert [item["period"] for item in history] == expected[: const.MONTH_HISTORY_MONTHS]
    assert set(history[0]) == PERIOD_KEYS


async def test_all_twenty_seven_sensors_are_registered_with_the_prefix(hass):
    entry = await setup_vehicle(hass)

    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)

    assert len(SENSOR_KEYS) == 27
    assert len(entities) == 27
    for entity in entities:
        assert entity.entity_id.startswith(f"sensor.{const.ENTITY_PREFIX}_")
    assert {hass.states.get(entity.entity_id).attributes["key"] for entity in entities} == set(
        SENSOR_KEYS
    )


async def test_month_sensors_report_the_frozen_current_month(hass, freezer, utc_timezone):
    freezer.move_to(datetime(2026, 2, 15, 12, 0, tzinfo=UTC))
    entry = await setup_vehicle(hass)
    await add_fillup(
        hass, entry.entry_id, 40, 60.0, odometer=BASE_ODOMETER, date=JANUARY.isoformat()
    )
    await add_fillup(
        hass, entry.entry_id, 45, 67.5, odometer=BASE_ODOMETER + 500, date=FEBRUARY.isoformat()
    )

    assert sensor_value(hass, const.SENSOR_MONTH_LITERS) == 45.0
    assert sensor_value(hass, const.SENSOR_MONTH_COST) == 67.5
    assert sensor_value(hass, const.SENSOR_MONTH_FILL_COUNT) == 1.0
    assert sensor_value(hass, const.SENSOR_MONTH_DISTANCE) == 500.0
    assert sensor_value(hass, const.SENSOR_MONTH_AVG_CONSUMPTION) == 9.0

    for key in MONTH_KEYS:
        assert sensor_state(hass, key).attributes["month"] == "2026-02"


async def test_current_month_without_fillups_is_zero_and_unknown(hass, freezer, utc_timezone):
    """A month that has not been refuelled in yet: honest zeros, unknown rates."""
    freezer.move_to(datetime(2026, 2, 15, 12, 0, tzinfo=UTC))
    entry = await setup_vehicle(hass)
    await add_fillup(
        hass, entry.entry_id, 40, 60.0, odometer=BASE_ODOMETER, date=JANUARY.isoformat()
    )

    assert float(sensor_state(hass, const.SENSOR_MONTH_LITERS).state) == 0.0
    assert float(sensor_state(hass, const.SENSOR_MONTH_COST).state) == 0.0
    assert float(sensor_state(hass, const.SENSOR_MONTH_FILL_COUNT).state) == 0.0
    assert sensor_state(hass, const.SENSOR_MONTH_AVG_CONSUMPTION).state == "unknown"
    assert sensor_state(hass, const.SENSOR_MONTH_DISTANCE).state == "unknown"
    assert sensor_state(hass, const.SENSOR_MONTH_COST).attributes["month"] == "2026-02"


async def test_current_month_that_closes_no_leg_has_unknown_consumption(
    hass, freezer, utc_timezone
):
    """Purchases are known; distance and consumption are not."""
    freezer.move_to(datetime(2026, 2, 15, 12, 0, tzinfo=UTC))
    entry = await setup_vehicle(hass)
    await add_fillup(
        hass, entry.entry_id, 40, 60.0, odometer=BASE_ODOMETER, date=FEBRUARY.isoformat()
    )

    assert sensor_value(hass, const.SENSOR_MONTH_LITERS) == 40.0
    assert sensor_value(hass, const.SENSOR_MONTH_COST) == 60.0
    assert sensor_value(hass, const.SENSOR_MONTH_FILL_COUNT) == 1.0
    assert sensor_state(hass, const.SENSOR_MONTH_DISTANCE).state == "unknown"
    assert sensor_state(hass, const.SENSOR_MONTH_AVG_CONSUMPTION).state == "unknown"


async def test_monthly_resets_carry_no_state_class(hass):
    """Feeding a monthly reset into long-term statistics would corrupt the sum."""
    await setup_vehicle(hass)
    registry = er.async_get(hass)
    capabilities = {
        state.attributes["key"]: registry.async_get(state.entity_id).capabilities
        for state in hass.states.async_all("sensor")
    }

    for key in (
        const.SENSOR_MONTH_DISTANCE,
        const.SENSOR_MONTH_LITERS,
        const.SENSOR_MONTH_COST,
        const.SENSOR_MONTH_FILL_COUNT,
    ):
        assert "state_class" not in (capabilities[key] or {}), key

    assert capabilities[const.SENSOR_MONTH_AVG_CONSUMPTION]["state_class"] == "measurement"
