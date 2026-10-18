"""Period statistics: the payload contract, years, the rolling window and the
sensors that report them.

Contract: ``docs/ARCHITECTURE.md`` "Period statistics".
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from custom_components.fuelusagetracker import const
from custom_components.fuelusagetracker.data import FuelUsage, PeriodUsage
from tests.helpers import (
    BASE_ODOMETER,
    PERIOD_KEYS,
    add_fillup,
    fill,
    sensor_state,
    sensor_value,
    setup_vehicle,
)

CARD_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "custom_components/fuelusagetracker/frontend/fuelusagetracker-card.js"
)

JANUARY = datetime(2026, 1, 10, 9, 0, tzinfo=UTC)
FROZEN_FEBRUARY = datetime(2026, 2, 15, 12, 0, tzinfo=UTC)
#: The fixture below runs 2025-05..2026-06, so it rolls its window from June.
FROZEN_JUNE = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)

ROLLING_KEYS = (
    const.SENSOR_ROLLING_DISTANCE,
    const.SENSOR_ROLLING_LITERS,
    const.SENSOR_ROLLING_COST,
    const.SENSOR_ROLLING_AVG_CONSUMPTION,
)
YEAR_KEYS = (
    const.SENSOR_YEAR_DISTANCE,
    const.SENSOR_YEAR_LITERS,
    const.SENSOR_YEAR_COST,
    const.SENSOR_YEAR_AVG_CONSUMPTION,
)


def months_of(index: int) -> datetime:
    """The 15th of the month ``index`` months after May 2025."""
    year, month = 2025 + (4 + index) // 12, (4 + index) % 12 + 1
    return datetime(year, month, 15, 12, 0, tzinfo=UTC)


def test_period_payload_has_exactly_the_contracted_keys():
    """A key nothing renders must not creep back into the payload."""
    assert set(PeriodUsage(key="2026-01").as_dict()) == PERIOD_KEYS


def test_every_period_payload_key_is_read_by_the_card():
    """The card is the only consumer: an unrendered payload key is a bug."""
    source = CARD_SOURCE.read_text(encoding="utf-8")

    unrendered = [
        key
        for key in PeriodUsage(key="2026-01").as_dict()
        if not re.search(rf"\b{re.escape(key)}\b", source)
    ]

    assert not unrendered, f"period payload key(s) the card never reads: {unrendered}"


def test_years_group_by_calendar_year_newest_first_with_the_same_rules(utc_timezone):
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0, date=datetime(2025, 6, 1, 9, 0, tzinfo=UTC), fillup_id="a"),
            fill(45, 10500.0, date=datetime(2025, 7, 1, 9, 0, tzinfo=UTC), fillup_id="b"),
            fill(30, 11000.0, date=datetime(2026, 3, 1, 9, 0, tzinfo=UTC), fillup_id="c"),
            fill(
                10,
                11200.0,
                full=False,
                date=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
                fillup_id="d",
            ),
        ]
    )

    years = {year.key: year for year in usage.years()}

    assert list(years) == ["2026", "2025"]
    assert years["2025"].liters == 85.0
    assert years["2025"].fill_count == 2
    assert years["2025"].distance == 500.0
    assert years["2025"].leg_liters == 45.0
    assert years["2025"].avg_consumption == 9.0
    # 2026 bought 40 L, but the leg closed that year is the 30 L of the full fill.
    assert years["2026"].liters == 40.0
    assert years["2026"].fill_count == 2
    assert years["2026"].distance == 500.0
    assert years["2026"].leg_liters == 30.0
    assert years["2026"].avg_consumption == 6.0


def test_current_year_is_zeroed_without_a_fillup_this_year(utc_timezone, freezer):
    freezer.move_to(FROZEN_FEBRUARY)
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0, date=datetime(2025, 6, 1, 9, 0, tzinfo=UTC), fillup_id="a")
        ]
    )

    current = usage.current_year

    assert current.key == "2026"
    assert (current.liters, current.cost, current.fill_count) == (0.0, 0.0, 0)
    assert current.distance is None
    assert current.avg_consumption is None


def test_rolling_window_is_the_trailing_twelve_months(utc_timezone, freezer):
    freezer.move_to(FROZEN_JUNE)
    # 14 consecutive months, 2025-05 .. 2026-06, one 100 km leg per fill.
    usage = FuelUsage(
        fillups=[
            fill(
                40.0,
                BASE_ODOMETER + 100 * index,
                date=months_of(index),
                fillup_id=f"m{index}",
            )
            for index in range(14)
        ]
    )

    window = usage.rolling()

    assert window.key == "2025-07..2026-06"
    assert len(usage.months()) == 14
    assert [month.key for month in usage.months()][:2] == ["2026-06", "2026-05"]
    # The two months before the window (2025-05, 2025-06) are dropped.
    assert window.fill_count == 12
    assert window.liters == 12 * 40.0
    assert window.cost == 12 * 60.0
    assert window.distance == 12 * 100.0
    assert window.leg_liters == 12 * 40.0
    assert window.avg_consumption == 40.0


def test_an_empty_month_inside_the_window_contributes_nothing(utc_timezone, freezer):
    freezer.move_to(FROZEN_JUNE)
    # The same 14 months, minus 2026-01: a hole inside the window.
    usage = FuelUsage(
        fillups=[
            fill(
                40.0,
                BASE_ODOMETER + 100 * index,
                date=months_of(index),
                fillup_id=f"m{index}",
            )
            for index in range(14)
            if index != 8
        ]
    )

    window = usage.rolling()

    assert "2026-01" not in {month.key for month in usage.months()}
    assert window.key == "2025-07..2026-06"
    assert window.fill_count == 11
    assert window.liters == 11 * 40.0
    # The hole only widens the leg that spans it (100 km -> 200 km).
    assert window.distance == 1200.0
    assert window.avg_consumption == 36.67


def test_a_window_that_closes_no_leg_reports_none_distance(utc_timezone, freezer):
    freezer.move_to(FROZEN_FEBRUARY)
    usage = FuelUsage(
        fillups=[fill(40.0, 10000.0, date=JANUARY, fillup_id="f0")]
    )

    window = usage.rolling()

    assert window.key == "2025-03..2026-02"
    assert window.fill_count == 1
    assert window.liters == 40.0
    assert window.distance is None
    assert window.avg_consumption is None


def test_an_empty_vehicle_rolls_a_zero_window(utc_timezone, freezer):
    freezer.move_to(FROZEN_FEBRUARY)

    window = FuelUsage().rolling()

    assert window.key == "2025-03..2026-02"
    assert (window.liters, window.cost, window.fill_count) == (0.0, 0.0, 0)
    assert window.distance is None
    assert window.avg_consumption is None


def test_year_bucketing_uses_local_time(zagreb_timezone):
    """23:30 UTC on 31 December is already the next year in a UTC+1 zone."""
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0, date=datetime(2026, 12, 31, 23, 30, tzinfo=UTC), fillup_id="f0")
        ]
    )

    assert [year.key for year in usage.years()] == ["2027"]


def test_year_bucketing_stays_in_the_same_year_under_utc(utc_timezone):
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0, date=datetime(2026, 12, 31, 23, 30, tzinfo=UTC), fillup_id="f0")
        ]
    )

    assert [year.key for year in usage.years()] == ["2026"]


async def test_rolling_and_year_sensors_report_the_periods_they_name(
    hass, freezer, utc_timezone
):
    freezer.move_to(FROZEN_FEBRUARY)
    entry = await setup_vehicle(hass)
    # The January fill is last year, so the 12-month window and the year differ.
    await add_fillup(
        hass,
        entry.entry_id,
        40,
        60.0,
        odometer=BASE_ODOMETER,
        date="2025-12-10T09:00:00+00:00",
    )
    await add_fillup(
        hass,
        entry.entry_id,
        45,
        67.5,
        odometer=BASE_ODOMETER + 500,
        date="2026-02-10T09:00:00+00:00",
    )

    assert sensor_value(hass, const.SENSOR_ROLLING_LITERS) == 85.0
    assert sensor_value(hass, const.SENSOR_ROLLING_COST) == 127.5
    assert sensor_value(hass, const.SENSOR_ROLLING_DISTANCE) == 500.0
    assert sensor_value(hass, const.SENSOR_ROLLING_AVG_CONSUMPTION) == 9.0
    for key in ROLLING_KEYS:
        assert sensor_state(hass, key).attributes["window"] == "2025-03..2026-02"

    assert sensor_value(hass, const.SENSOR_YEAR_LITERS) == 45.0
    assert sensor_value(hass, const.SENSOR_YEAR_COST) == 67.5
    assert sensor_value(hass, const.SENSOR_YEAR_DISTANCE) == 500.0
    assert sensor_value(hass, const.SENSOR_YEAR_AVG_CONSUMPTION) == 9.0
    for key in YEAR_KEYS:
        assert sensor_state(hass, key).attributes["year"] == "2026"


async def test_year_cost_history_is_capped_newest_first_and_well_shaped(hass):
    """12 years in, YEAR_HISTORY_YEARS newest-first rows out."""
    entry = await setup_vehicle(hass)
    coordinator = entry.runtime_data
    years = list(range(2015, 2027))

    for index, year in enumerate(years):
        await coordinator.async_add_fillup(
            fill(
                40.0,
                BASE_ODOMETER + index * 100,
                date=datetime(year, 6, 15, 12, 0, tzinfo=UTC),
                fillup_id=f"y{year}",
            )
        )
    await hass.async_block_till_done()

    history = sensor_state(hass, const.SENSOR_YEAR_COST).attributes["years"]

    assert len(history) == const.YEAR_HISTORY_YEARS == 10
    assert [row["period"] for row in history] == [str(year) for year in reversed(years)][:10]
    assert set(history[0]) == PERIOD_KEYS


async def test_month_payload_survived_the_period_rename(hass, freezer, utc_timezone):
    freezer.move_to(FROZEN_FEBRUARY)
    entry = await setup_vehicle(hass)
    await add_fillup(
        hass, entry.entry_id, 40, 60.0, odometer=BASE_ODOMETER, date=JANUARY.isoformat()
    )

    month_cost = sensor_state(hass, const.SENSOR_MONTH_COST)

    assert month_cost.attributes["month"] == "2026-02"
    assert set(month_cost.attributes["months"][0]) == PERIOD_KEYS
