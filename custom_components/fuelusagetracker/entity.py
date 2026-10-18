"""Shared entity plumbing for Fuel Usage Tracker."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENGINE, CONF_FUEL_TYPE, DOMAIN, ENTITY_PREFIX, NAME
from .data import FuelUsageCoordinator, vehicle_settings


class FuelUsageEntity(CoordinatorEntity[FuelUsageCoordinator]):
    """Base class for every entity of a tracked vehicle.

    The device name carries the integration prefix, so every generated entity_id
    looks like ``sensor.fuelusagetracker_<vehicle>_<key>``.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: FuelUsageCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        settings = vehicle_settings(entry)
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{ENTITY_PREFIX} {entry.title}",
            manufacturer=NAME,
            model=settings.get(CONF_ENGINE) or NAME,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Identity attributes, also used by the bundled Lovelace card."""
        entry = self.coordinator.entry
        settings = vehicle_settings(entry)
        return {
            "key": self._key,
            "vehicle": entry.entry_id,
            "vehicle_name": entry.title,
            "fuel_type": settings.get(CONF_FUEL_TYPE),
            "engine": settings.get(CONF_ENGINE),
        }
