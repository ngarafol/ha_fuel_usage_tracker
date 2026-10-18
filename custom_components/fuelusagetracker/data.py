"""Data model, storage and coordinator for Fuel Usage Tracker."""

from __future__ import annotations

import logging
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
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


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
    def first_odometer(self) -> float | None:
        readings = self._odometer_readings()
        return readings[0] if readings else None

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

    def _legs(self) -> list[tuple[float, float]]:
        """Full-to-full legs as (liters, distance) pairs.

        Tank-to-tank method: a leg ends at a full tank fill-up with an odometer
        reading and contains every litre added since the previous full tank,
        including partial fill-ups in between. A full tank without an odometer
        reading breaks the chain, because the distance of that leg is unknown.
        """
        legs: list[tuple[float, float]] = []
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
                    legs.append((liters, distance))
            previous = (index, fill.odometer)
        return legs

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

    async def async_update(self, fillup_id: str, changes: dict[str, Any]) -> FillUp | None:
        """Update one fill-up in place; returns None when the id is unknown."""
        for index, fill in enumerate(self.fillups):
            if fill.id != fillup_id:
                continue
            updated = FillUp(
                id=fill.id,
                date=changes.get("date", fill.date),
                liters=changes.get("liters", fill.liters),
                price=changes.get("price", fill.price),
                odometer=changes.get("odometer", fill.odometer),
                full=changes.get("full", fill.full),
                station=changes.get("station", fill.station),
                notes=changes.get("notes", fill.notes),
            )
            self.fillups[index] = updated
            self.fillups.sort(key=lambda item: item.date)
            await self._async_save()
            return updated
        return None

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

    async def async_update_fillup(
        self, fillup_id: str, changes: dict[str, Any]
    ) -> FillUp | None:
        """Update a stored fill-up and publish the recomputed statistics."""
        result = await self.store.async_update(fillup_id, changes)
        if result is not None:
            self.async_set_updated_data(self._usage())
        return result

    async def async_delete_fillup(self, fillup_id: str) -> bool:
        """Delete a stored fill-up and publish the recomputed statistics."""
        deleted = await self.store.async_delete(fillup_id)
        if deleted:
            self.async_set_updated_data(self._usage())
        return deleted
