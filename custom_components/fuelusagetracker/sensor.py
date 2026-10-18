"""Sensor platform for the Fuel Usage Tracker integration.

One entity per row of the frozen sensor key table in ``docs/ARCHITECTURE.md``.
The three tables below transcribe that contract — device class, state class,
unit and value — so keep them in sync with ``const.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    SENSOR_AVG_CONSUMPTION,
    SENSOR_AVG_PRICE_PER_LITER,
    SENSOR_COST_PER_KM,
    SENSOR_FILL_COUNT,
    SENSOR_KM_SINCE_LAST_FILL,
    SENSOR_LAST_CONSUMPTION,
    SENSOR_LAST_FILL,
    SENSOR_LAST_FILL_COST,
    SENSOR_LAST_FILL_LITERS,
    SENSOR_LAST_PRICE_PER_LITER,
    SENSOR_ODOMETER,
    SENSOR_TOTAL_COST,
    SENSOR_TOTAL_DISTANCE,
    SENSOR_TOTAL_LITERS,
)
from .data import FuelUsage, FuelUsageCoordinator
from .entity import FuelUsageEntity

if TYPE_CHECKING:
    from . import FuelUsageConfigEntry

#: HA limits attribute size, so the card's fill-up history is capped.
_MAX_FILLUPS: Final = 50

#: Device class, state class and (static) unit of every sensor; `–` cells are None.
SENSOR_DESCRIPTIONS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key=SENSOR_ODOMETER,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="km",
    ),
    SensorEntityDescription(
        key=SENSOR_KM_SINCE_LAST_FILL,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="km",
    ),
    SensorEntityDescription(
        key=SENSOR_TOTAL_DISTANCE,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="km",
    ),
    SensorEntityDescription(
        key=SENSOR_TOTAL_LITERS,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="L",
    ),
    SensorEntityDescription(
        key=SENSOR_TOTAL_COST,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=SENSOR_AVG_PRICE_PER_LITER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_LAST_FILL,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key=SENSOR_LAST_FILL_COST,
        device_class=SensorDeviceClass.MONETARY,
    ),
    SensorEntityDescription(
        key=SENSOR_LAST_FILL_LITERS,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        native_unit_of_measurement="L",
    ),
    SensorEntityDescription(
        key=SENSOR_LAST_PRICE_PER_LITER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_LAST_CONSUMPTION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="L/100km",
    ),
    SensorEntityDescription(
        key=SENSOR_AVG_CONSUMPTION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="L/100km",
    ),
    SensorEntityDescription(
        key=SENSOR_COST_PER_KM,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(key=SENSOR_FILL_COUNT),
)

#: Where each sensor reads its value, as a dotted path on `data.FuelUsage`.
_VALUE_PATHS: Final[dict[str, str]] = {
    SENSOR_ODOMETER: "odometer",
    SENSOR_KM_SINCE_LAST_FILL: "km_since_last_fill",
    SENSOR_TOTAL_DISTANCE: "total_distance",
    SENSOR_TOTAL_LITERS: "total_liters",
    SENSOR_TOTAL_COST: "total_cost",
    SENSOR_AVG_PRICE_PER_LITER: "avg_price_per_liter",
    SENSOR_LAST_FILL: "last_fill.date",
    SENSOR_LAST_FILL_COST: "last_fill.price",
    SENSOR_LAST_FILL_LITERS: "last_fill.liters",
    SENSOR_LAST_PRICE_PER_LITER: "last_price_per_liter",
    SENSOR_LAST_CONSUMPTION: "last_consumption",
    SENSOR_AVG_CONSUMPTION: "avg_consumption",
    SENSOR_COST_PER_KM: "cost_per_km",
    SENSOR_FILL_COUNT: "fill_count",
}

#: Units that embed the global `hass.config.currency`.
_CURRENCY_UNITS: Final[dict[str, str]] = {
    SENSOR_TOTAL_COST: "{currency}",
    SENSOR_LAST_FILL_COST: "{currency}",
    SENSOR_AVG_PRICE_PER_LITER: "{currency}/L",
    SENSOR_LAST_PRICE_PER_LITER: "{currency}/L",
    SENSOR_COST_PER_KM: "{currency}/km",
}


def _dotted_value(root: Any, path: str) -> Any:
    """Follow a dotted attribute path, giving up as soon as a link is None."""
    value = root
    for part in path.split("."):
        if value is None:
            return None
        value = getattr(value, part)
    return value


class FuelUsageSensor(FuelUsageEntity, SensorEntity):
    """One computed statistic of a tracked vehicle."""

    entity_description: SensorEntityDescription

    def __init__(
        self, coordinator: FuelUsageCoordinator, description: SensorEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        unit = _CURRENCY_UNITS.get(description.key)
        self._attr_native_unit_of_measurement = (
            unit.format(currency=coordinator.hass.config.currency)
            if unit is not None
            else description.native_unit_of_measurement
        )

    @property
    def native_value(self) -> Any:
        """Current value, or None (rendered as `unknown`) when not computable."""
        return _dotted_value(
            self.coordinator.data, _VALUE_PATHS[self.entity_description.key]
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Identity attributes, plus the fill-up history on the `last_fill` sensor."""
        attributes = super().extra_state_attributes
        if self.entity_description.key != SENSOR_LAST_FILL:
            return attributes
        usage: FuelUsage = self.coordinator.data
        last = usage.last_fill
        attributes.update(
            fillup_id=last.id if last else None,
            liters=last.liters if last else None,
            price=last.price if last else None,
            price_per_liter=last.price_per_liter if last else None,
            odometer=last.odometer if last else None,
            station=last.station if last else None,
            full=last.full if last else None,
            notes=last.notes if last else None,
            fillups=[
                fill.as_dict() for fill in reversed(usage.fillups[-_MAX_FILLUPS:])
            ],
        )
        return attributes


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FuelUsageConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up every sensor of one vehicle."""
    coordinator = entry.runtime_data
    async_add_entities(
        FuelUsageSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )
