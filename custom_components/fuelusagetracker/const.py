"""Constants for the Fuel Usage Tracker integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "fuelusagetracker"
NAME: Final = "Fuel Usage Tracker"

#: Prefix used for every device name, and therefore for every generated entity_id.
#: Guarantees entity_ids of the form ``sensor.fuelusagetracker_<vehicle>_<key>``.
ENTITY_PREFIX: Final = "fuelusagetracker"

STORAGE_VERSION: Final = 1

# Config / options keys (vehicle settings).
CONF_NAME: Final = "name"
CONF_FUEL_TYPE: Final = "fuel_type"
CONF_ENGINE: Final = "engine"
CONF_ODOMETER: Final = "odometer"

# Service field keys.
CONF_VEHICLE: Final = "vehicle"
CONF_LITERS: Final = "liters"
CONF_PRICE: Final = "price"
CONF_DATE: Final = "date"
CONF_FULL: Final = "full"
CONF_STATION: Final = "station"
CONF_NOTES: Final = "notes"
CONF_FILLUP_ID: Final = "fillup_id"

#: Supported fuel types; the values are translation keys, never shown raw.
FUEL_TYPES: Final[tuple[str, ...]] = (
    "petrol",
    "diesel",
    "lpg",
    "cng",
    "hybrid",
    "electric",
    "other",
)

SERVICE_ADD_FILLUP: Final = "add_fillup"
SERVICE_UPDATE_FILLUP: Final = "update_fillup"
SERVICE_DELETE_FILLUP: Final = "delete_fillup"
SERVICE_UPDATE_VEHICLE: Final = "update_vehicle"

# Sensor keys. These are stable identifiers: they are exposed as the ``key`` state
# attribute so the bundled Lovelace card never has to guess entity_ids.
SENSOR_ODOMETER: Final = "odometer"
SENSOR_KM_SINCE_LAST_FILL: Final = "km_since_last_fill"
SENSOR_TOTAL_DISTANCE: Final = "total_distance"
SENSOR_TOTAL_LITERS: Final = "total_liters"
SENSOR_TOTAL_COST: Final = "total_cost"
SENSOR_AVG_PRICE_PER_LITER: Final = "avg_price_per_liter"
SENSOR_LAST_FILL: Final = "last_fill"
SENSOR_LAST_FILL_COST: Final = "last_fill_cost"
SENSOR_LAST_FILL_LITERS: Final = "last_fill_liters"
SENSOR_LAST_PRICE_PER_LITER: Final = "last_price_per_liter"
SENSOR_LAST_CONSUMPTION: Final = "last_consumption"
SENSOR_AVG_CONSUMPTION: Final = "avg_consumption"
SENSOR_COST_PER_KM: Final = "cost_per_km"
SENSOR_FILL_COUNT: Final = "fill_count"
