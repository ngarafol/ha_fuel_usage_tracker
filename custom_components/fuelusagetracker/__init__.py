"""The Fuel Usage Tracker integration.

Tracks refuelling for one or more vehicles: cost, litres, consumption and
odometer based distances. Every vehicle is a config entry and a device; the
bundled Lovelace card is the intended UI.
"""

from __future__ import annotations

import logging
from uuid import uuid4

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DATE,
    CONF_ENGINE,
    CONF_FILENAME,
    CONF_FILLUP_ID,
    CONF_FUEL_TYPE,
    CONF_FULL,
    CONF_LITERS,
    CONF_NAME,
    CONF_NOTES,
    CONF_ODOMETER,
    CONF_PRICE,
    CONF_SCOPE,
    CONF_STATION,
    CONF_VEHICLE,
    DOMAIN,
    EXPORT_SCOPES,
    FUEL_TYPES,
    SERVICE_ADD_FILLUP,
    SERVICE_DELETE_FILLUP,
    SERVICE_EXPORT_CSV,
    SERVICE_UPDATE_VEHICLE,
)
from .csv_export import ENCODING, build_csv, csv_path
from .data import FillUp, FuelUsageCoordinator
from .frontend import async_setup_frontend

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type FuelUsageConfigEntry = ConfigEntry[FuelUsageCoordinator]

ADD_FILLUP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VEHICLE): cv.string,
        vol.Required(CONF_LITERS): vol.All(vol.Coerce(float), vol.Range(min=0.001)),
        vol.Required(CONF_PRICE): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional(CONF_ODOMETER): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional(CONF_DATE): cv.datetime,
        vol.Optional(CONF_FULL, default=True): cv.boolean,
        vol.Optional(CONF_STATION): cv.string,
        vol.Optional(CONF_NOTES): cv.string,
    }
)

DELETE_FILLUP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VEHICLE): cv.string,
        vol.Required(CONF_FILLUP_ID): cv.string,
    }
)

UPDATE_VEHICLE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VEHICLE): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_FUEL_TYPE): vol.In(FUEL_TYPES),
        vol.Optional(CONF_ENGINE): cv.string,
        vol.Optional(CONF_ODOMETER): vol.All(vol.Coerce(float), vol.Range(min=0)),
    }
)

EXPORT_CSV_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VEHICLE): cv.string,
        vol.Optional(CONF_SCOPE, default="fillups"): vol.In(EXPORT_SCOPES),
        vol.Optional(CONF_FILENAME): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: FuelUsageConfigEntry) -> bool:
    """Set up one vehicle from a config entry."""
    coordinator = FuelUsageCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_frontend(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FuelUsageConfigEntry) -> bool:
    """Unload a vehicle config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when the vehicle settings change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_get_entry(hass: HomeAssistant, vehicle: str) -> ConfigEntry:
    """Resolve a vehicle by config entry id or name."""
    needle = vehicle.casefold().strip()
    entries = hass.config_entries.async_entries(DOMAIN)
    for entry in entries:
        if needle in (entry.entry_id.casefold(), entry.title.casefold()):
            return entry
    known = ", ".join(entry.title for entry in entries) or "none"
    raise HomeAssistantError(f"Unknown vehicle '{vehicle}' (known vehicles: {known})")


def _async_get_coordinator(hass: HomeAssistant, vehicle: str) -> FuelUsageCoordinator:
    entry = _async_get_entry(hass, vehicle)
    coordinator: FuelUsageCoordinator | None = getattr(entry, "runtime_data", None)
    if coordinator is None:
        raise HomeAssistantError(f"Vehicle '{entry.title}' is not loaded yet")
    return coordinator


@callback
def _async_register_services(hass: HomeAssistant) -> None:
    """Register the integration services once."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_FILLUP):
        return

    async def async_add_fillup(call: ServiceCall) -> None:
        coordinator = _async_get_coordinator(call.hass, call.data[CONF_VEHICLE])
        fillup = FillUp(
            id=uuid4().hex,
            date=call.data.get(CONF_DATE) or dt_util.utcnow(),
            liters=call.data[CONF_LITERS],
            price=call.data[CONF_PRICE],
            odometer=call.data.get(CONF_ODOMETER),
            full=call.data[CONF_FULL],
            station=call.data.get(CONF_STATION),
            notes=call.data.get(CONF_NOTES),
        )
        await coordinator.async_add_fillup(fillup)
        _LOGGER.debug(
            "Recorded fill-up %s for %s (%s L, %s)",
            fillup.id,
            coordinator.entry.title,
            fillup.liters,
            fillup.price,
        )

    async def async_delete_fillup(call: ServiceCall) -> None:
        coordinator = _async_get_coordinator(call.hass, call.data[CONF_VEHICLE])
        if not await coordinator.async_delete_fillup(call.data[CONF_FILLUP_ID]):
            raise HomeAssistantError(
                f"Unknown fill-up id '{call.data[CONF_FILLUP_ID]}'"
            )

    async def async_update_vehicle(call: ServiceCall) -> None:
        entry = _async_get_entry(call.hass, call.data[CONF_VEHICLE])
        options = dict(entry.options)
        for key in (CONF_FUEL_TYPE, CONF_ENGINE, CONF_ODOMETER):
            if key in call.data:
                options[key] = call.data[key]
        title = call.data.get(CONF_NAME) or entry.title
        if title != entry.title or options != entry.options:
            call.hass.config_entries.async_update_entry(
                entry, title=title, options=options
            )

    async def async_export_csv(call: ServiceCall) -> ServiceResponse:
        entry = _async_get_entry(call.hass, call.data[CONF_VEHICLE])
        scope = call.data[CONF_SCOPE]
        coordinator = _async_get_coordinator(call.hass, call.data[CONF_VEHICLE])
        text, rows = build_csv(coordinator.data, scope)
        path = csv_path(call.hass, entry.title, scope, call.data.get(CONF_FILENAME))
        await call.hass.async_add_executor_job(path.write_text, text, ENCODING)
        _LOGGER.info("Exported %s %s rows to %s", rows, scope, path)
        return {"path": str(path), "rows": rows}

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_FILLUP, async_add_fillup, schema=ADD_FILLUP_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_FILLUP, async_delete_fillup, schema=DELETE_FILLUP_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_VEHICLE, async_update_vehicle, schema=UPDATE_VEHICLE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_CSV,
        async_export_csv,
        schema=EXPORT_CSV_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
