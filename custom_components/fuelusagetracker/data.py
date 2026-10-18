"""Data model, storage and coordinator for Fuel Usage Tracker."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ODOMETER,
    DOMAIN,
    ROLLING_MONTHS,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def month_key(year: int, month: int, delta: int = 0) -> str:
    """Return the sortable ``YYYY-MM`` key of a month, shifted by ``delta`` months."""
    index = year * 12 + month - 1 + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def vehicle_settings(entry: ConfigEntry) -> dict[str, Any]:
    """Return merged vehicle settings; options win over the initial config data."""
    return {**entry.data, **entry.options}


def to_float(value: Any) -> float | None:
    """Return value as float, or None when it is not a usable number."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class FillUp:
    """A single refuelling event."""

    id: str
    date: datetime
    liters: float
    price: float
    odometer: float | None = None
    full: bool = True
    station: str | None = None
    notes: str | None = None

    @property
    def price_per_liter(self) -> float | None:
        """Price of one litre for this fill-up."""
        return self.price / self.liters if self.liters else None

    def as_dict(self) -> dict[str, Any]:
        """Serialise for the storage file."""
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "liters": self.liters,
            "price": self.price,
            "odometer": self.odometer,
            "full": self.full,
            "station": self.station,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FillUp:
        """Build a fill-up from storage data."""
        date = dt_util.parse_datetime(str(data.get("date"))) or dt_util.utcnow()
        return cls(
            id=str(data.get("id") or uuid4().hex),
            date=date,
            liters=float(data.get("liters") or 0),
            price=float(data.get("price") or 0),
            odometer=to_float(data.get("odometer")),
            full=bool(data.get("full", True)),
            station=data.get("station"),
            notes=data.get("notes"),
        )


@dataclass(slots=True)
class PeriodUsage:
    """Aggregated usage of one period: a calendar month, a year or a rolling window."""

    key: str
    liters: float = 0.0
    cost: float = 0.0
    fill_count: int = 0
    #: Litres and kilometres of the tank-to-tank legs closed inside this period.
    leg_liters: float = 0.0
    distance: float | None = None

    @property
    def avg_consumption(self) -> float | None:
        """Litres per 100 km over the legs closed in this period."""
        if not self.distance:
            return None
        return round(self.leg_liters / self.distance * 100, 2)

    def as_dict(self) -> dict[str, Any]:
        """Serialise for an entity attribute (the card compares periods with this)."""
        return {
            "period": self.key,
            "distance": round(self.distance, 1) if self.distance is not None else None,
            "liters": round(self.liters, 3),
            "cost": round(self.cost, 2),
            "avg_consumption": self.avg_consumption,
            "fill_count": self.fill_count,
        }


@dataclass(slots=True)
class FuelUsage:
    """Computed statistics for one vehicle."""

    fillups: list[FillUp] = field(default_factory=list)
    baseline_odometer: float | None = None

    @property
    def fill_count(self) -> int:
        return len(self.fillups)

    @property
    def total_liters(self) -> float:
        return round(sum(fill.liters for fill in self.fillups), 3)

    @property
    def total_cost(self) -> float:
        return round(sum(fill.price for fill in self.fillups), 2)

    @property
    def avg_price_per_liter(self) -> float | None:
        return self.total_cost / self.total_liters if self.total_liters else None

    @property
    def last_fill(self) -> FillUp | None:
        return self.fillups[-1] if self.fillups else None

    @property
    def last_price_per_liter(self) -> float | None:
        last = self.last_fill
        return last.price_per_liter if last else None

    def _odometer_readings(self) -> list[float]:
        readings = [fill.odometer for fill in self.fillups if fill.odometer is not None]
        if self.baseline_odometer is not None:
            readings.append(self.baseline_odometer)
        return sorted(readings)

    @property
    def odometer(self) -> float | None:
        """Last known odometer reading."""
        readings = self._odometer_readings()
        return readings[-1] if readings else None

    @property
    def total_distance(self) -> float | None:
        """Distance covered between the first and the last known odometer reading."""
        readings = self._odometer_readings()
        if len(readings) < 2:
            return None
        return round(readings[-1] - readings[0], 1)

    @property
    def km_since_last_fill(self) -> float | None:
        """Distance covered since the last fill-up that recorded an odometer value."""
        last_with_odometer = next(
            (fill for fill in reversed(self.fillups) if fill.odometer is not None), None
        )
        odometer = self.odometer
        if last_with_odometer is None or odometer is None:
            return None
        return round(odometer - last_with_odometer.odometer, 1)

    def _leg_rows(self) -> list[tuple[int, float, float]]:
        """Tank-to-tank legs as (closing fill-up index, liters, distance) rows.

        Tank-to-tank method: a leg ends at a full tank fill-up with an odometer
        reading and contains every litre added since the previous full tank,
        including partial fill-ups in between. A full tank without an odometer
        reading breaks the chain, because the distance of that leg is unknown.
        """
        rows: list[tuple[int, float, float]] = []
        previous: tuple[int, float] | None = None
        for index, fill in enumerate(self.fillups):
            if not fill.full:
                continue
            if fill.odometer is None:
                previous = None
                continue
            if previous is not None:
                prev_index, prev_odometer = previous
                distance = fill.odometer - prev_odometer
                if distance > 0:
                    liters = sum(item.liters for item in self.fillups[prev_index + 1 : index + 1])
                    rows.append((index, liters, distance))
            previous = (index, fill.odometer)
        return rows

    def _legs(self) -> list[tuple[float, float]]:
        """Full-to-full legs as (liters, distance) pairs."""
        return [(liters, distance) for _, liters, distance in self._leg_rows()]

    @property
    def avg_consumption(self) -> float | None:
        """Litres per 100 km over every measured full-to-full leg."""
        legs = self._legs()
        distance = sum(leg[1] for leg in legs)
        if not distance:
            return None
        return round(sum(leg[0] for leg in legs) / distance * 100, 2)

    @property
    def last_consumption(self) -> float | None:
        """Litres per 100 km over the most recent measured leg."""
        legs = self._legs()
        if not legs:
            return None
        liters, distance = legs[-1]
        return round(liters / distance * 100, 2)

    @property
    def cost_per_km(self) -> float | None:
        """Fuel cost per kilometre over the measured distance."""
        distance = sum(leg[1] for leg in self._legs())
        if not distance:
            return None
        return round(self.total_cost / distance, 4)

    def _periods(self, key_of: Callable[[datetime], str]) -> dict[str, PeriodUsage]:
        """Aggregate fill-ups and their closed legs into periods.

        Bucketing uses the fill-up date in Home Assistant's local time, so a
        late-evening fill-up belongs to the day and period the driver experienced.
        Distance and leg litres come from the tank-to-tank legs closed in the
        period; litres, cost and the fill-up count are what was purchased.
        """
        periods: dict[str, PeriodUsage] = {}
        legs = {index: (liters, distance) for index, liters, distance in self._leg_rows()}
        for index, fill in enumerate(self.fillups):
            key = key_of(dt_util.as_local(fill.date))
            period = periods.setdefault(key, PeriodUsage(key=key))
            period.liters += fill.liters
            period.cost += fill.price
            period.fill_count += 1
            if (leg := legs.get(index)) is not None:
                period.leg_liters += leg[0]
                period.distance = (period.distance or 0.0) + leg[1]
        return periods

    def months(self) -> list[PeriodUsage]:
        """Every month that has at least one fill-up, newest first."""
        periods = self._periods(lambda local: month_key(local.year, local.month))
        return sorted(periods.values(), key=lambda period: period.key, reverse=True)

    def years(self) -> list[PeriodUsage]:
        """Every calendar year that has at least one fill-up, newest first."""
        periods = self._periods(lambda local: f"{local.year:04d}")
        return sorted(periods.values(), key=lambda period: period.key, reverse=True)

    def rolling(self, count: int = ROLLING_MONTHS) -> PeriodUsage:
        """Trailing ``count`` calendar months, ending with the current one.

        Includes the current (possibly incomplete) month, so the window always
        ends today. Empty months inside the window simply contribute nothing.
        """
        now = dt_util.now()
        first, last = month_key(now.year, now.month, 1 - count), month_key(now.year, now.month)
        window = PeriodUsage(key=f"{first}..{last}")
        for period in self.months():
            if not first <= period.key <= last:
                continue
            window.liters += period.liters
            window.cost += period.cost
            window.fill_count += period.fill_count
            window.leg_liters += period.leg_liters
            if period.distance is not None:
                window.distance = (window.distance or 0.0) + period.distance
        return window

    @property
    def current_month(self) -> PeriodUsage:
        """This calendar month in local time; zeroed when it has no fill-up yet."""
        now = dt_util.now()
        key = month_key(now.year, now.month)
        return next(
            (period for period in self.months() if period.key == key),
            PeriodUsage(key=key),
        )

    @property
    def current_year(self) -> PeriodUsage:
        """This calendar year in local time; zeroed when it has no fill-up yet."""
        key = f"{dt_util.now().year:04d}"
        return next(
            (period for period in self.years() if period.key == key),
            PeriodUsage(key=key),
        )



class FuelUsageStore:
    """Persistent per-vehicle fill-up storage."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}"
        )
        self.loaded = False
        self.fillups: list[FillUp] = []

    async def async_load(self) -> None:
        """Load fill-ups from disk once."""
        if self.loaded:
            return
        data = await self._store.async_load() or {}
        self.fillups = sorted(
            (FillUp.from_dict(item) for item in data.get("fillups", [])),
            key=lambda fill: fill.date,
        )
        self.loaded = True

    async def async_add(self, fillup: FillUp) -> FillUp:
        self.fillups.append(fillup)
        self.fillups.sort(key=lambda fill: fill.date)
        await self._async_save()
        return fillup

    async def async_delete(self, fillup_id: str) -> bool:
        """Delete one fill-up; returns False when the id is unknown."""
        remaining = [fill for fill in self.fillups if fill.id != fillup_id]
        if len(remaining) == len(self.fillups):
            return False
        self.fillups = remaining
        await self._async_save()
        return True

    async def _async_save(self) -> None:
        await self._store.async_save(
            {"fillups": [fill.as_dict() for fill in self.fillups]}
        )


class FuelUsageCoordinator(DataUpdateCoordinator[FuelUsage]):
    """Owns the fill-ups of a single vehicle and recomputes its statistics."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.title}",
            update_interval=None,
        )
        self.entry = entry
        self.store = FuelUsageStore(hass, entry.entry_id)

    def _usage(self) -> FuelUsage:
        return FuelUsage(
            fillups=list(self.store.fillups),
            baseline_odometer=to_float(vehicle_settings(self.entry).get(CONF_ODOMETER)),
        )

    async def _async_update_data(self) -> FuelUsage:
        await self.store.async_load()
        return self._usage()

    async def async_add_fillup(self, fillup: FillUp) -> FillUp:
        """Store a new fill-up and publish the recomputed statistics."""
        result = await self.store.async_add(fillup)
        self.async_set_updated_data(self._usage())
        return result

    async def async_delete_fillup(self, fillup_id: str) -> bool:
        """Delete a stored fill-up and publish the recomputed statistics."""
        deleted = await self.store.async_delete(fillup_id)
        if deleted:
            self.async_set_updated_data(self._usage())
        return deleted
