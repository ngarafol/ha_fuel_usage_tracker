"""Fill-up maths: which fills form a measurable full-to-full leg.

Tank-to-tank method (docs/ARCHITECTURE.md): a leg runs from one full-tank
fill-up with an odometer to the next one and contains every litre added in
between, partial fill-ups included. Only a full-tank fill-up without an
odometer breaks the chain.
"""

from __future__ import annotations

from custom_components.fuelusagetracker.data import FuelUsage
from tests.helpers import fill


def test_two_full_fills_with_odometer_measure_consumption():
    usage = FuelUsage(
        fillups=[fill(40, 10000.0), fill(45, 10500.0)],
        baseline_odometer=10000.0,
    )

    assert usage.last_consumption == 9.0
    assert usage.avg_consumption == 9.0
    assert usage.total_distance == 500.0


def test_partial_fill_is_folded_into_the_leg():
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0),
            fill(10, 10250.0, full=False),
            fill(45, 10500.0),
        ],
        baseline_odometer=10000.0,
    )

    assert usage.total_liters == 95.0
    assert usage.total_distance == 500.0
    # 10 L partial + 45 L full = 55 L over 500 km. The 40 L of the first
    # full-tank fill-up refilled the tank, it is never part of a leg.
    assert usage.avg_consumption == 11.0
    assert usage.last_consumption == 11.0


def test_partial_fill_after_the_last_full_fill_adds_litres_only():
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0),
            fill(45, 10500.0),
            fill(10, 10600.0, full=False),
        ],
        baseline_odometer=10000.0,
    )

    assert usage.total_liters == 95.0
    assert usage.total_distance == 600.0
    # The trailing partial fill neither opens nor closes a leg.
    assert usage.last_consumption == 9.0
    assert usage.avg_consumption == 9.0


def test_full_fill_without_odometer_resets_the_leg_chain():
    broken = FuelUsage(
        fillups=[
            fill(40, 10000.0),
            fill(30, None),
            fill(45, 10500.0),
        ],
        baseline_odometer=10000.0,
    )
    restarted = FuelUsage(
        fillups=[
            fill(40, 10000.0),
            fill(30, None),
            fill(45, 10500.0),
            fill(40, 11000.0),
        ],
        baseline_odometer=10000.0,
    )

    assert broken.last_consumption is None
    assert broken.avg_consumption is None
    # The chain restarts at the next full tank with an odometer reading, so the
    # 30 L and 40 L before the reset are never attributed to a leg.
    assert restarted.last_consumption == 8.0
    assert restarted.avg_consumption == 8.0


def test_consumption_is_unknown_without_odometer_readings():
    usage = FuelUsage(fillups=[fill(40, None), fill(45, None)])

    assert usage.last_consumption is None
    assert usage.avg_consumption is None
    assert usage.odometer is None
    assert usage.total_distance is None
    assert usage.total_liters == 85.0


def test_cost_per_100km_counts_burned_fuel_not_total_spend():
    """The opening tank is the baseline; only the closing fill was burned."""
    usage = FuelUsage(
        fillups=[fill(40, 10000.0, price=60.0), fill(45, 10500.0, price=70.0)],
        baseline_odometer=10000.0,
    )

    # 70 EUR burned over 500 km; total spend over the same distance would be 26.0.
    assert usage.cost_per_100km == 14.0
    assert usage.total_cost == 130.0
    assert usage.avg_consumption == 9.0
    assert usage.last_consumption == 9.0


def test_cost_per_100km_ignores_the_fuel_bought_but_not_yet_burned():
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0, price=60.0),
            fill(45, 10500.0, price=70.0),
            fill(10, 10600.0, full=False, price=15.0),
        ],
        baseline_odometer=10000.0,
    )

    # The trailing partial fill buys fuel for the next leg: not in the rate yet.
    assert usage.cost_per_100km == 14.0
    assert usage.total_cost == 145.0


def test_cost_per_100km_includes_a_partial_fill_inside_the_leg():
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0, price=60.0),
            fill(10, 10250.0, full=False, price=15.0),
            fill(45, 10500.0, price=70.0),
        ],
        baseline_odometer=10000.0,
    )

    # 15 + 70 = 85 EUR burned over the 500 km leg.
    assert usage.cost_per_100km == 17.0
    assert usage.avg_consumption == 11.0
    assert usage.last_consumption == 11.0


def test_cost_per_100km_is_unknown_without_a_measured_leg():
    single = FuelUsage(fillups=[fill(40, 10000.0, price=60.0)])
    unmeasured = FuelUsage(
        fillups=[fill(40, None, price=60.0), fill(45, None, price=70.0)]
    )

    assert single.cost_per_100km is None
    assert unmeasured.cost_per_100km is None
    # Purchases are still reported, even when no rate can be computed.
    assert single.total_cost == 60.0
    assert single.total_liters == 40.0
    assert unmeasured.total_cost == 130.0
    assert unmeasured.total_liters == 85.0


def test_last_leg_distance_is_the_most_recent_measured_leg():
    two = FuelUsage(
        fillups=[fill(40, 10000.0), fill(45, 10500.0)], baseline_odometer=10000.0
    )
    three = FuelUsage(
        fillups=[fill(40, 10000.0), fill(45, 10500.0), fill(40, 10800.0)],
        baseline_odometer=10000.0,
    )

    assert two.last_leg_distance == 500.0
    assert three.last_leg_distance == 300.0
    assert FuelUsage(fillups=[fill(40, 10000.0)]).last_leg_distance is None


def test_consumed_metrics_exclude_the_starting_tank_and_the_newest_purchase():
    usage = FuelUsage(
        fillups=[fill(40, 10000.0, price=60.0), fill(45, 10500.0, price=70.0)],
        baseline_odometer=10000.0,
    )

    # Only the closing fill was burned; the opening tank is the baseline and the
    # newest purchase fuels the next leg.
    assert usage.consumed_liters == 45.0
    assert usage.consumed_cost == 70.0
    assert usage.total_liters == 85.0
    assert usage.total_cost == 130.0


def test_consumed_metrics_include_a_partial_fill_inside_the_leg():
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0, price=60.0),
            fill(10, 10250.0, full=False, price=15.0),
            fill(45, 10500.0, price=70.0),
        ],
        baseline_odometer=10000.0,
    )

    assert usage.consumed_liters == 55.0
    assert usage.consumed_cost == 85.0
    assert usage.total_liters == 95.0
    assert usage.total_cost == 145.0


def test_consumed_metrics_are_zero_without_a_measured_leg():
    single = FuelUsage(fillups=[fill(40, 10000.0, price=60.0)])
    unmeasured = FuelUsage(
        fillups=[fill(40, None, price=60.0), fill(45, None, price=70.0)]
    )

    # Zero, not unknown: the car burned nothing we can measure yet. And a float,
    # never the int 0 an empty sum would produce.
    assert single.consumed_liters == 0.0
    assert single.consumed_cost == 0.0
    assert isinstance(single.consumed_liters, float)
    assert isinstance(single.consumed_cost, float)
    assert unmeasured.consumed_liters == 0.0
    assert unmeasured.consumed_cost == 0.0
    assert single.total_cost == 60.0
    assert unmeasured.total_liters == 85.0


def test_range_full_tank_scales_the_capacity_by_the_average_consumption():
    canonical = FuelUsage(
        fillups=[fill(40, 10000.0, price=60.0), fill(45, 10500.0, price=70.0)],
        baseline_odometer=10000.0,
        tank_liters=55.0,
    )
    partial = FuelUsage(
        fillups=[
            fill(40, 10000.0, price=60.0),
            fill(10, 10250.0, full=False, price=15.0),
            fill(45, 10500.0, price=70.0),
        ],
        baseline_odometer=10000.0,
        tank_liters=55.0,
    )

    # 55 L at 9.0 and 11.0 L/100km.
    assert canonical.range_full_tank == 611.0
    assert partial.range_full_tank == 500.0


def test_range_full_tank_is_unknown_without_a_capacity_or_a_leg():
    canonical = [fill(40, 10000.0), fill(45, 10500.0)]

    # No capacity, a zero capacity and no closed leg are all unknown rather than
    # a division error.
    assert FuelUsage(fillups=canonical).range_full_tank is None
    assert FuelUsage(fillups=canonical, tank_liters=0.0).range_full_tank is None
    assert (
        FuelUsage(fillups=[fill(40, 10000.0)], tank_liters=55.0).range_full_tank is None
    )


def test_fillup_rows_annotate_only_the_fill_that_closed_a_leg():
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0, price=60.0, fillup_id="first"),
            fill(10, 10250.0, full=False, price=15.0, fillup_id="partial"),
            fill(45, 10500.0, price=70.0, fillup_id="closing"),
        ],
        baseline_odometer=10000.0,
    )

    closing, partial, first = usage.fillup_rows()

    assert [row["id"] for row in usage.fillup_rows()] == [
        "closing",
        "partial",
        "first",
    ]
    assert closing["leg_liters"] == 55.0
    assert closing["leg_distance"] == 500.0
    assert closing["leg_cost"] == 85.0
    assert closing["leg_consumption"] == 11.0
    assert not [key for key in partial if key.startswith("leg_")]
    assert not [key for key in first if key.startswith("leg_")]


def test_fillup_rows_limit_keeps_the_newest_and_still_annotates_them():
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0, price=60.0, fillup_id="first"),
            fill(10, 10250.0, full=False, price=15.0, fillup_id="partial"),
            fill(45, 10500.0, price=70.0, fillup_id="closing"),
        ],
        baseline_odometer=10000.0,
    )

    rows = usage.fillup_rows(2)

    assert [row["id"] for row in rows] == ["closing", "partial"]
    assert rows[0]["leg_distance"] == 500.0
    assert "leg_distance" not in rows[1]
