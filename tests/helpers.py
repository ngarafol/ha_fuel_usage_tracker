"""Small helpers shared by the Fuel Usage Tracker tests."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fuelusagetracker import const
from custom_components.fuelusagetracker.data import FillUp

#: Baseline odometer (km) of the test vehicle, so distances are deterministic.
BASE_ODOMETER = 10000.0

DEFAULT_VEHICLE: dict[str, Any] = {
    const.CONF_NAME: "Premcar",
    const.CONF_FUEL_TYPE: "diesel",
    const.CONF_ENGINE: "1.6 HDi",
    const.CONF_ODOMETER: BASE_ODOMETER,
}

#: The 19 sensor keys of the frozen key table, taken from const.py itself.
SENSOR_KEYS: frozenset[str] = frozenset(
    value for name, value in vars(const).items() if name.startswith("SENSOR_")
)

FILLUP_DATE_1 = "2026-01-10T09:00:00+00:00"
FILLUP_DATE_MID = "2026-01-20T09:00:00+00:00"
FILLUP_DATE_2 = "2026-02-10T09:00:00+00:00"

#: Fallback instant for fixture fill-ups whose date the test does not care about.
FILLUP_BASE_DATE = datetime.fromisoformat(FILLUP_DATE_1)


def fill(
    liters: float,
    odometer: float | None = None,
    full: bool = True,
    *,
    date: datetime = FILLUP_BASE_DATE,
    fillup_id: str = "fill",
) -> FillUp:
    """Build a fill-up priced at 1.50 per litre, the shared fixture convention.

    ``date`` and ``fillup_id`` default to a fixed anchor, so a maths-only test
    can stay terse; any test that buckets by month passes its own ``date``.
    """
    return FillUp(
        id=fillup_id,
        date=date,
        liters=liters,
        price=liters * 1.5,
        odometer=odometer,
        full=full,
    )


def make_entry(**overrides: Any) -> MockConfigEntry:
    """Build a config entry for a vehicle."""
    data = {**DEFAULT_VEHICLE, **overrides}
    return MockConfigEntry(
        domain=const.DOMAIN, title=data[const.CONF_NAME], data=data, options={}
    )


async def setup_vehicle(
    hass: HomeAssistant, entry: MockConfigEntry | None = None
) -> MockConfigEntry:
    """Add an entry to hass and set it up."""
    entry = entry or make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def sensor_state(hass: HomeAssistant, key: str):
    """Return the sensor state that carries ``key`` in its attributes."""
    for state in hass.states.async_all("sensor"):
        if state.attributes.get("key") == key:
            return state
    raise AssertionError(f"no sensor exposes key {key!r}")


def sensor_value(hass: HomeAssistant, key: str) -> float:
    """Return the numeric state of the sensor with ``key``."""
    return float(sensor_state(hass, key).state)


async def call_service(
    hass: HomeAssistant, service: str, data: dict[str, Any]
) -> None:
    """Call an integration service and wait for the state machine to settle."""
    await hass.services.async_call(const.DOMAIN, service, data, blocking=True)
    await hass.async_block_till_done()


async def add_fillup(
    hass: HomeAssistant,
    vehicle: str,
    liters: float,
    price: float,
    **fields: Any,
) -> None:
    """Record a fill-up through the add_fillup service."""
    await call_service(
        hass,
        const.SERVICE_ADD_FILLUP,
        {
            const.CONF_VEHICLE: vehicle,
            const.CONF_LITERS: liters,
            const.CONF_PRICE: price,
            **fields,
        },
    )


async def two_full_fillups(hass: HomeAssistant, vehicle: str) -> None:
    """Add the canonical leg: 40 L @ 10000 km then 45 L @ 10500 km."""
    await add_fillup(
        hass, vehicle, 40, 60.0, odometer=BASE_ODOMETER, date=FILLUP_DATE_1
    )
    await add_fillup(
        hass, vehicle, 45, 67.5, odometer=BASE_ODOMETER + 500, date=FILLUP_DATE_2
    )
