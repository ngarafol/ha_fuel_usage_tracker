"""Sensor platform for the Fuel Usage Tracker integration.

One entity per row of the frozen sensor key table in ``docs/ARCHITECTURE.md``.
``SENSOR_DESCRIPTIONS`` is the single source of truth: device class, state class,
unit and value of every sensor live in that one tuple, so keep it in sync with
``const.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    MONTH_HISTORY_MONTHS,
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
    SENSOR_MONTH_AVG_CONSUMPTION,
    SENSOR_MONTH_COST,
    SENSOR_MONTH_DISTANCE,
    SENSOR_MONTH_FILL_COUNT,
    SENSOR_MONTH_LITERS,
    SENSOR_ODOMETER,
    SENSOR_ROLLING_AVG_CONSUMPTION,
    SENSOR_ROLLING_COST,
    SENSOR_ROLLING_DISTANCE,
    SENSOR_ROLLING_LITERS,
    SENSOR_TOTAL_COST,
    SENSOR_TOTAL_DISTANCE,
    SENSOR_TOTAL_LITERS,
    SENSOR_YEAR_AVG_CONSUMPTION,
    SENSOR_YEAR_COST,
    SENSOR_YEAR_DISTANCE,
    SENSOR_YEAR_LITERS,
    YEAR_HISTORY_YEARS,
)
from .data import FuelUsage, FuelUsageCoordinator
from .entity import FuelUsageEntity

if TYPE_CHECKING:
    from . import FuelUsageConfigEntry

#: HA limits attribute size, so the card's fill-up history is capped.
_MAX_FILLUPS: Final = 50

#: The period a sensor's value belongs to; the card labels it with that period's key.
PeriodKind = Literal["month", "rolling", "year"]


@dataclass(frozen=True, kw_only=True)
class FuelUsageSensorDescription(SensorEntityDescription):
    """A sensor of one vehicle, complete including how to read its value.

    ``SensorEntityDescription`` has no ``value_fn`` field, so the callable lives
    on this subclass — the same pattern core integrations use (e.g. ``abode``).
    """

    #: Reads the value off `data.FuelUsage`; None makes HA render `unknown`.
    value_fn: Callable[[FuelUsage], Any]
    #: Unit template with a `{currency}` placeholder, when it embeds the currency.
    unit_template: str | None = None
    #: Carries the period key as an attribute: `month`, `window` or `year`.
    period_kind: PeriodKind | None = None


SENSOR_DESCRIPTIONS: Final[tuple[FuelUsageSensorDescription, ...]] = (
    FuelUsageSensorDescription(
        key=SENSOR_ODOMETER,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="km",
        value_fn=lambda usage: usage.odometer,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_KM_SINCE_LAST_FILL,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="km",
        value_fn=lambda usage: usage.km_since_last_fill,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_TOTAL_DISTANCE,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="km",
        value_fn=lambda usage: usage.total_distance,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_TOTAL_LITERS,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="L",
        value_fn=lambda usage: usage.total_liters,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_TOTAL_COST,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        unit_template="{currency}",
        value_fn=lambda usage: usage.total_cost,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_AVG_PRICE_PER_LITER,
        state_class=SensorStateClass.MEASUREMENT,
        unit_template="{currency}/L",
        value_fn=lambda usage: usage.avg_price_per_liter,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_LAST_FILL,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda usage: usage.last_fill.date if usage.last_fill else None,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_LAST_FILL_COST,
        device_class=SensorDeviceClass.MONETARY,
        unit_template="{currency}",
        value_fn=lambda usage: usage.last_fill.price if usage.last_fill else None,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_LAST_FILL_LITERS,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        native_unit_of_measurement="L",
        value_fn=lambda usage: usage.last_fill.liters if usage.last_fill else None,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_LAST_PRICE_PER_LITER,
        state_class=SensorStateClass.MEASUREMENT,
        unit_template="{currency}/L",
        value_fn=lambda usage: usage.last_price_per_liter,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_LAST_CONSUMPTION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="L/100km",
        value_fn=lambda usage: usage.last_consumption,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_AVG_CONSUMPTION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="L/100km",
        value_fn=lambda usage: usage.avg_consumption,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_COST_PER_KM,
        state_class=SensorStateClass.MEASUREMENT,
        unit_template="{currency}/km",
        value_fn=lambda usage: usage.cost_per_km,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_FILL_COUNT,
        value_fn=lambda usage: usage.fill_count,
    ),
    # Current-month values. Deliberately no state_class: they reset every month,
    # so long-term statistics would sum garbage — the `total_*` sensors own those.
    FuelUsageSensorDescription(
        key=SENSOR_MONTH_DISTANCE,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement="km",
        period_kind="month",
        value_fn=lambda usage: usage.current_month.distance,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_MONTH_LITERS,
        native_unit_of_measurement="L",
        period_kind="month",
        value_fn=lambda usage: usage.current_month.liters,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_MONTH_COST,
        device_class=SensorDeviceClass.MONETARY,
        unit_template="{currency}",
        period_kind="month",
        value_fn=lambda usage: usage.current_month.cost,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_MONTH_AVG_CONSUMPTION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="L/100km",
        period_kind="month",
        value_fn=lambda usage: usage.current_month.avg_consumption,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_MONTH_FILL_COUNT,
        period_kind="month",
        value_fn=lambda usage: usage.current_month.fill_count,
    ),
    # Rolling window and year values: no state_class either, they slide or reset.
    FuelUsageSensorDescription(
        key=SENSOR_ROLLING_DISTANCE,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement="km",
        period_kind="rolling",
        value_fn=lambda usage: usage.rolling().distance,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_ROLLING_LITERS,
        native_unit_of_measurement="L",
        period_kind="rolling",
        value_fn=lambda usage: usage.rolling().liters,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_ROLLING_COST,
        device_class=SensorDeviceClass.MONETARY,
        unit_template="{currency}",
        period_kind="rolling",
        value_fn=lambda usage: usage.rolling().cost,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_ROLLING_AVG_CONSUMPTION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="L/100km",
        period_kind="rolling",
        value_fn=lambda usage: usage.rolling().avg_consumption,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_YEAR_DISTANCE,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement="km",
        period_kind="year",
        value_fn=lambda usage: usage.current_year.distance,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_YEAR_LITERS,
        native_unit_of_measurement="L",
        period_kind="year",
        value_fn=lambda usage: usage.current_year.liters,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_YEAR_COST,
        device_class=SensorDeviceClass.MONETARY,
        unit_template="{currency}",
        period_kind="year",
        value_fn=lambda usage: usage.current_year.cost,
    ),
    FuelUsageSensorDescription(
        key=SENSOR_YEAR_AVG_CONSUMPTION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="L/100km",
        period_kind="year",
        value_fn=lambda usage: usage.current_year.avg_consumption,
    ),
)


class FuelUsageSensor(FuelUsageEntity, SensorEntity):
    """One computed statistic of a tracked vehicle."""

    entity_description: FuelUsageSensorDescription

    def __init__(
        self, coordinator: FuelUsageCoordinator, description: FuelUsageSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        unit = description.unit_template
        self._attr_native_unit_of_measurement = (
            unit.format(currency=coordinator.hass.config.currency)
            if unit is not None
            else description.native_unit_of_measurement
        )

    @property
    def native_value(self) -> Any:
        """Current value, or None (rendered as `unknown`) when not computable."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Identity attributes, plus the period/history some sensors carry."""
        attributes = super().extra_state_attributes
        description = self.entity_description
        key = description.key
        usage: FuelUsage = self.coordinator.data
        if description.period_kind == "month":
            attributes["month"] = usage.current_month.key
            if key == SENSOR_MONTH_COST:
                attributes["months"] = [
                    period.as_dict() for period in usage.months()[:MONTH_HISTORY_MONTHS]
                ]
            return attributes
        if description.period_kind == "rolling":
            attributes["window"] = usage.rolling().key
            return attributes
        if description.period_kind == "year":
            attributes["year"] = usage.current_year.key
            if key == SENSOR_YEAR_COST:
                attributes["years"] = [
                    period.as_dict() for period in usage.years()[:YEAR_HISTORY_YEARS]
                ]
            return attributes
        if key != SENSOR_LAST_FILL:
            return attributes
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
