# Fuel Usage Tracker — architecture & frozen contract

Home Assistant custom integration that tracks vehicle refuelling: cost, litres,
consumption and odometer based distances. Domain: **`fuelusagetracker`**.

Everything written by the agent team on 2026-10-18 is bound by the contract in
this document. Change it here first, then change code.

## Repo layout & ownership

| Path | Owner | Purpose |
| --- | --- | --- |
| `custom_components/fuelusagetracker/manifest.json` | lead | integration manifest, holds the version |
| `custom_components/fuelusagetracker/const.py` | lead | domain, config/service field names, sensor keys |
| `custom_components/fuelusagetracker/data.py` | lead | `FillUp`, `FuelUsage` (consumption maths), storage, coordinator |
| `custom_components/fuelusagetracker/entity.py` | lead | base entity (device info, identity attributes) |
| `custom_components/fuelusagetracker/__init__.py` | lead | setup, services, frontend wiring |
| `custom_components/fuelusagetracker/config_flow.py` | config flow dev | add vehicle (user step) + edit vehicle (options step) |
| `custom_components/fuelusagetracker/sensor.py` | sensor dev | one sensor platform, entities from the key table |
| `custom_components/fuelusagetracker/frontend.py` | card dev | serve + auto-register the card |
| `custom_components/fuelusagetracker/frontend/fuelusagetracker-card.js` | card dev | the Lovelace card |
| `custom_components/fuelusagetracker/{strings.json,translations/,services.yaml}` | config flow dev | translations & service UI |
| `tests/`, `pytest.ini`, `requirements_test.txt` | test dev | automated checks |
| `README.md`, `CHANGELOG.md`, `hacs.json`, `docs/` | lead | docs & versioning |

## Vehicle model (one config entry = one vehicle = one device)

Config/options keys: `name` (also the entry title), `fuel_type`
(`petrol|diesel|lpg|cng|hybrid|electric|other`), `engine` (free text),
`odometer` (baseline odometer in km, float).

`vehicle_settings(entry)` in `data.py` merges `entry.data` with `entry.options`
(options win) — always use it instead of reading `entry.data` directly.

## Fill-up model

`data.FillUp(id, date, liters, price, odometer=None, full=True, station=None, notes=None)`

* `price` is the **total paid** for that fill-up (not per litre);
  `price_per_liter` is derived.
* `odometer` is optional. Consumption uses the **tank-to-tank method**: a leg
  runs from one full-tank fill-up with an odometer reading to the next one and
  contains every litre added in between, partial fill-ups included. A full-tank
  fill-up without an odometer reading breaks the chain, because that leg's
  distance is unknown.

`data.FuelUsage` exposes the computed values used by sensors:
`fill_count`, `total_liters`, `total_cost`, `avg_price_per_liter`, `last_fill`,
`last_price_per_liter`, `odometer`, `first_odometer`, `total_distance`,
`km_since_last_fill`, `avg_consumption`, `last_consumption`, `cost_per_km`.
Each returns `None` when it cannot be computed (sensor state must then be
`unknown`).

Persistence: one HA `Store` file per entry (`fuelusagetracker.<entry_id>`),
version `1`, shape `{"fillups": [<fill-up dict>]}`.

## Services

| Service | Fields |
| --- | --- |
| `fuelusagetracker.add_fillup` | `vehicle` (required, entry id or title), `liters` (required, > 0), `price` (required, total, >= 0), `odometer` (>= 0), `date` (datetime), `full` (bool, default `true`), `station`, `notes` |
| `fuelusagetracker.update_fillup` | `vehicle`, `fillup_id` + any subset of `liters`, `price`, `odometer`, `date`, `full`, `station`, `notes` |
| `fuelusagetracker.delete_fillup` | `vehicle`, `fillup_id` |
| `fuelusagetracker.update_vehicle` | `vehicle` + any subset of `name`, `fuel_type`, `engine`, `odometer` |

Unknown vehicle or unknown fill-up id raises `HomeAssistantError`.

## Entities

* One platform: `sensor`. Every entity extends `entity.FuelUsageEntity`.
* `FuelUsageEntity._attr_has_entity_name = True` and the device name is
  `fuelusagetracker <entry title>`; combined with `_attr_translation_key = <key>`
  this yields entity ids of the form `sensor.fuelusagetracker_<vehicle>_<key>`.
* Every entity carries these state attributes: `key`, `vehicle` (config entry
  id), `vehicle_name`, `fuel_type`, `engine`. The card relies on them.

Sensor key table (keys are defined in `const.py`, names come from
`entity.sensor.<key>.name`):

| key | device_class | state_class | unit | value |
| --- | --- | --- | --- | --- |
| `odometer` | distance | total_increasing | km | `usage.odometer` |
| `km_since_last_fill` | distance | measurement | km | `usage.km_since_last_fill` |
| `total_distance` | distance | total_increasing | km | `usage.total_distance` |
| `total_liters` | – | total | L | `usage.total_liters` |
| `total_cost` | monetary | total | currency | `usage.total_cost` |
| `avg_price_per_liter` | – | measurement | `<currency>/L` | `usage.avg_price_per_liter` |
| `last_fill` | timestamp | – | – | `usage.last_fill.date` |
| `last_fill_cost` | monetary | – | currency | `usage.last_fill.price` |
| `last_fill_liters` | volume_storage | – | L | `usage.last_fill.liters` |
| `last_price_per_liter` | – | measurement | `<currency>/L` | `usage.last_price_per_liter` |
| `last_consumption` | – | measurement | `L/100km` | `usage.last_consumption` |
| `avg_consumption` | – | measurement | `L/100km` | `usage.avg_consumption` |
| `cost_per_km` | – | measurement | `<currency>/km` | `usage.cost_per_km` |
| `fill_count` | – | – | – | `usage.fill_count` |

`<currency>` is `hass.config.currency`.

The device_class/state_class pairs above are the only ones Home Assistant
2026.2.3 accepts (`homeassistant/components/sensor/const.py`,
`DEVICE_CLASS_STATE_CLASSES`): `monetary` allows only `total` and
`volume_storage` only `measurement`, so `total_liters` carries no device class
and uses `total`, which keeps the long-term statistics sum working.

A vehicle without any fill-up reports `fill_count`, `total_liters` and
`total_cost` as `0` (an honest sum over nothing); every other value is `unknown`
because it cannot be computed yet.

The `last_fill` sensor additionally exposes, for the card:

* `fillup_id`, `liters`, `price`, `price_per_liter`, `odometer`, `station`,
  `full`, `notes` of the newest fill-up;
* `fillups`: the newest first list of fill-up dicts (shape of
  `FillUp.as_dict()`), **capped at the 50 newest** because HA limits attribute
  size.

## Lovelace card

`fuelusagetracker-card`, a single vanilla-JS file (no build step), defined in
`frontend/fuelusagetracker-card.js`, registered as an extra frontend module by
`frontend.py` (`async_setup_frontend(hass)`, called by `__init__.py`).

Card config: `entity` (any entity of a vehicle) or `vehicle` (config entry id or
vehicle name); with no config it shows the first tracked vehicle and offers a
picker. It must:

* read stats from entities via the `key` attribute (never from guessed entity ids),
* list recent fill-ups from the `fillups` attribute of the `last_fill` entity,
* add a fill-up through `fuelusagetracker.add_fillup`,
* update the odometer through `fuelusagetracker.update_vehicle`,
* delete a fill-up through `fuelusagetracker.delete_fillup`, with a confirmation
  dialog (destructive action).

Entity ids are additional decoration only: the card must work when entity ids
were renamed by the user.

## Checks (no exceptions)

```bash
.venv/bin/python -m pytest -q                 # HA integration tests
.venv/bin/python -m py_compile custom_components/fuelusagetracker/*.py
node --check custom_components/fuelusagetracker/frontend/fuelusagetracker-card.js
```

## Roadmap (phase 2, not implemented)

Receipt OCR: run OCR over a photographed invoice, extract date/price/litres and
call the same `add_fillup` service. No code is written for this yet; the service
surface above is the seam it will plug into.
