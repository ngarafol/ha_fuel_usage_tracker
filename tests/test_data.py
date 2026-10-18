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
