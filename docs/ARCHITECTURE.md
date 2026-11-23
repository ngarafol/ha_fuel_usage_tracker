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
| `custom_components/fuelusagetracker/data.py` | lead | `FillUp`, `PeriodUsage`, `FuelUsage` (consumption maths), storage, coordinator |
| `custom_components/fuelusagetracker/sensor.py` | sensor dev | entity base (`FuelUsageEntity`) + the 27 sensor descriptions |
| `custom_components/fuelusagetracker/__init__.py` | lead | setup, services, frontend wiring |
| `custom_components/fuelusagetracker/config_flow.py` | config flow dev | add vehicle (user step) + edit vehicle (options step) |
| `custom_components/fuelusagetracker/frontend.py` | card dev | serve + auto-register the card |
| `custom_components/fuelusagetracker/frontend/fuelusagetracker-card.js` | card dev | the Lovelace card |
| `custom_components/fuelusagetracker/{strings.json,translations/,services.yaml}` | config flow dev | translations & service UI |
| `custom_components/fuelusagetracker/csv_export.py` | lead | CSV building + safe export path |
| `tests/`, `pytest.ini`, `requirements_test.txt` | test dev | automated checks |
| `docs/preview/card-preview.html`, `docs/images/card-*.png` | preview dev | card harness + light/dark screenshots |
| `docs/preview/make_diagrams.py`, `docs/images/{monthly-chart,yearly-chart,architecture}.png` | lead | chart & data-flow previews (the generated `*.html` pages are gitignored) |
| `README.md`, `CHANGELOG.md`, `hacs.json`, `docs/ARCHITECTURE.md` | lead | docs & versioning |

## Vehicle model (one config entry = one vehicle = one device)

Config/options keys: `name` (also the entry title), `fuel_type`
(`petrol|diesel|lpg|cng|hybrid|electric|other`), `engine` (free text),
`odometer` (odometer in km at the start of tracking, float) and
`tank_liters` (optional tank capacity in L, float; enables `range_full_tank`) and
`image` (optional URL of the vehicle photo, free text; exposed as `entity_picture`
on every sensor and used as the card's avatar).

`vehicle_settings(entry)` in `data.py` merges `entry.data` with `entry.options`
(options win) — always use it instead of reading `entry.data` directly. Entry
data is written by the config flow (`async_step_user`) and by the native
reconfigure flow (`async_step_reconfigure`), which also strips the vehicle keys
from `entry.options` so values an older install saved there cannot shadow the
new data. There is deliberately **no options flow**: it showed the same fields as
the wizard but wrote to a different dict.

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
`fill_count`, `total_liters`, `total_cost`, `avg_price_per_liter`,
`consumed_liters`, `consumed_cost`, `last_fill`, `last_price_per_liter`,
`odometer`, `total_distance`, `last_leg_distance`, `avg_consumption`,
`last_consumption`, `cost_per_100km`, `range_full_tank`, and
`fillup_rows(limit)` for the annotated fill-up payload.
Each returns `None` when it cannot be computed (sensor state must then be
`unknown`).

`_leg_rows()` returns `(closing fill-up index, liters, distance, cost)`; a leg's
`cost` is the money spent on the fuel that leg **burned** — the closing fill-up
plus every partial fill-up since the previous full tank. The first full tank is
the baseline (the tank the car arrived with) and never belongs to a leg, so its
spend is in `total_cost` but not in `cost_per_100km`. `cost_per_100km` is
`sum(leg costs) / sum(leg distances)`; the latest fill-up's fuel buys the *next*
leg, so it is excluded until the next full tank closes it. `total_cost` and
`total_liters` stay purchase-based (all money spent / all litres bought), and
`avg_price_per_liter` is the average purchase price — not the cost of driving.
`consumed_liters` and `consumed_cost` are the burned side: the sum of the legs'
litres and of the money spent on that fuel (they are 0 until a leg closes).
`range_full_tank` is `tank_liters / avg_consumption * 100` and only exists with
an optional capacity; it is the range of a *full* tank, not a live level.
`last_leg_distance` is the last measured leg's distance; there is deliberately no
"km since last fill" value, because odometers are entered at fill-ups, so it
would always be 0.

Persistence: one HA `Store` file per entry (`fuelusagetracker.<entry_id>`),
version `1`, shape `{"fillups": [<fill-up dict>]}`.

## Services

| Service | Fields |
| --- | --- |
| `fuelusagetracker.add_fillup` | `vehicle` (required, entry id or title), `liters` (required, > 0), `price` (required, total, >= 0), `odometer` (>= 0), `date` (datetime), `full` (bool, default `true`), `station`, `notes` |
| `fuelusagetracker.delete_fillup` | `vehicle`, `fillup_id` |
| `fuelusagetracker.update_vehicle` | `vehicle` + any subset of `name`, `fuel_type`, `engine`, `odometer` |
| `fuelusagetracker.export_csv` | `vehicle`, `scope` (`fillups` \| `months` \| `years`, default `fillups`), `filename` (plain `.csv` name, optional), `format` (`standard` \| `excel_hr`, default `standard`). Returns `{path, rows}` (`SupportsResponse.OPTIONAL`). |

Unknown vehicle or unknown fill-up id raises `HomeAssistantError`. `export_csv`
writes into the Home Assistant config directory only: a `filename` with a path
separator, a parent reference or a hidden-file prefix is rejected, and the
default name is `fuelusagetracker_<vehicle>_<scope>.csv`. The file is UTF-8 with
a BOM so Excel reads Croatian station names correctly. `format: standard` is
comma separated with dot decimals and LF endings (scripts, pandas);
`format: excel_hr` is semicolon separated with comma decimals and CRLF endings,
which is what Excel expects in a Croatian/European locale. Scheduling an export
is not integration code: Home Assistant automations trigger the service and any
`notify` target delivers the returned path (README recipe).

## Entities

* One platform: `sensor`; all 27 entities are `sensor.FuelUsageSensor`
  (`CoordinatorEntity` + `SensorEntity`), so they share the device info and the
  identity attributes below.
* `FuelUsageSensor._attr_has_entity_name = True` and the device name is
  `fuelusagetracker <entry title>`; combined with `_attr_translation_key = <key>`
  this yields entity ids of the form `sensor.fuelusagetracker_<vehicle>_<key>`.
* Every entity carries these state attributes: `key`, `vehicle` (config entry
  id), `vehicle_name`, `fuel_type`, `engine`. The card relies on them.

Sensor key table (keys are defined in `const.py`, names come from
`entity.sensor.<key>.name`):

| key | device_class | state_class | unit | value |
| --- | --- | --- | --- | --- |
| `odometer` | distance | total_increasing | km | `usage.odometer` |
| `distance_to_last_fill` | distance | measurement | km | `usage.last_leg_distance` |
| `range_full_tank` | distance | measurement | km | `usage.range_full_tank` |
| `total_distance` | distance | total_increasing | km | `usage.total_distance` |
| `total_liters` | – | total | L | `usage.total_liters` |
| `total_cost` | monetary | total | currency | `usage.total_cost` |
| `avg_price_per_liter` | – | measurement | `<currency>/L` | `usage.avg_price_per_liter` |
| `consumed_liters` | – | total | L | `usage.consumed_liters` |
| `consumed_cost` | monetary | total | currency | `usage.consumed_cost` |
| `last_fill` | timestamp | – | – | `usage.last_fill.date` |
| `last_fill_cost` | monetary | – | currency | `usage.last_fill.price` |
| `last_fill_liters` | volume_storage | – | L | `usage.last_fill.liters` |
| `last_price_per_liter` | – | measurement | `<currency>/L` | `usage.last_price_per_liter` |
| `last_consumption` | – | measurement | `L/100km` | `usage.last_consumption` |
| `avg_consumption` | – | measurement | `L/100km` | `usage.avg_consumption` |
| `cost_per_100km` | – | measurement | `<currency>/100km` | `usage.cost_per_100km` |
| `fill_count` | – | – | – | `usage.fill_count` |
| `month_distance` | distance | – | km | `usage.current_month.distance` |
| `month_liters` | – | – | L | `usage.current_month.liters` |
| `month_cost` | monetary | – | currency | `usage.current_month.cost` |
| `month_avg_consumption` | – | measurement | `L/100km` | `usage.current_month.avg_consumption` |
| `month_fill_count` | – | – | – | `usage.current_month.fill_count` |
| `rolling_distance` | distance | – | km | `usage.rolling().distance` |
| `rolling_liters` | – | – | L | `usage.rolling().liters` |
| `rolling_cost` | monetary | – | currency | `usage.rolling().cost` |
| `rolling_avg_consumption` | – | measurement | `L/100km` | `usage.rolling().avg_consumption` |
| `year_distance` | distance | – | km | `usage.current_year.distance` |
| `year_liters` | – | – | L | `usage.current_year.liters` |
| `year_cost` | monetary | – | currency | `usage.current_year.cost` |
| `year_avg_consumption` | – | measurement | `L/100km` | `usage.current_year.avg_consumption` |

(`<currency>` is `hass.config.currency`.) That is 27 sensors per vehicle.

## Period statistics (month, year, rolling window)

One aggregation serves all three period kinds. `data.PeriodUsage` carries
`key`, `liters`, `cost`, `fill_count`, `leg_liters` and `distance`;
`as_dict()` serialises it as **`period`, `distance`, `liters`, `cost`,
`avg_consumption`, `fill_count`** (the older `month` field name is gone, and
payload keys that nothing renders must not come back — see the audit lesson in
`CHANGELOG.md`).

`FuelUsage` exposes:

* `months()` / `years()` — every month or year with at least one fill-up,
  newest first, keyed `YYYY-MM` / `YYYY`;
* `rolling(count=ROLLING_MONTHS)` — one `PeriodUsage` for the trailing
  `count` calendar months **ending with the current (possibly incomplete)
  month**, keyed `"YYYY-MM..YYYY-MM"`. Empty months inside the window
  contribute nothing;
* `current_month` / `current_year` — this calendar month/year, zeroed when it
  has no fill-up yet.

Rules that apply to every period kind:

* Bucketing is by the fill-up date converted with `dt_util.as_local()`, i.e. in
  `hass.config.time_zone`. A fill-up at 23:30 UTC on 31 January belongs to
  February in `Europe/Zagreb`. Tests must set the default time zone explicitly.
* `liters`, `cost` and `fill_count` are what was **purchased** in the period.
* `distance`, `leg_liters` and therefore `avg_consumption` come from the
  tank-to-tank legs **closed** in the period (the leg's total litres over the
  leg's kilometres). A period that closes no leg has `distance = None` and
  `avg_consumption = None`.
* Periods without any fill-up are omitted from `months()`/`years()` rather than
  reported as zero (the rolling window is the exception: it is a fixed window,
  so an empty month inside it is simply absent, and an empty window reports
  zeros with `distance = None`).

The `month_*`, `year_*` and `rolling_*` sensors deliberately carry **no state
class** for their totals: those values reset (month/year) or slide (rolling), so
feeding them into long-term statistics would corrupt the sum. Only
`month_avg_consumption`, `year_avg_consumption` and `rolling_avg_consumption`
are `measurement`. The `total_*` sensors own the statistics. A README recipe
shows the native `utility_meter` alternative (`cycle: monthly`) for users who
want HA-native period statistics entities.

Attributes for the card (each `as_dict()` row is the 6-key period payload above):

* every `month_*` sensor: `month` = `YYYY-MM`; every `year_*`: `year` = `YYYY`;
  every `rolling_*`: `window` = `YYYY-MM..YYYY-MM`;
* `month_cost`: `months`, newest first, **capped at `MONTH_HISTORY_MONTHS` (24)**;
* `year_cost`: `years`, newest first, **capped at `YEAR_HISTORY_YEARS` (10)**.

Caps exist because Home Assistant limits attribute size.

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
* every sensor of a vehicle with a configured `image` carries `entity_picture`
  (HA Entity property), which HA renders in more-info; the card uses it as the
  hero background. Blank or missing values expose no `entity_picture` at all.
* `fillups`: the newest first list of fill-up dicts, at most 50; a full fill-up
  that closed a measured leg also carries `leg_liters`, `leg_distance`,
  `leg_cost` and `leg_consumption` (L/100 km) — the fuel that leg burned. Shape of
  `FillUp.as_dict()`), **capped at the 50 newest** because HA limits attribute
  size.

## Lovelace card

`fuelusagetracker-card`, a single vanilla-JS file (no build step), defined in
`frontend/fuelusagetracker-card.js`, registered as an extra frontend module by
`frontend.py` (`async_setup_frontend(hass)`, called by `__init__.py`).

Card config: `entity` (any entity of a vehicle) or `vehicle` (config entry id or
vehicle name); with no config it shows the first tracked vehicle and offers a
picker. It must:

* open with the glow header (avatar, name, headline average consumption, 12-month
  bar mini-chart and the vs-12-month delta), a row of chips for the rest, two
  period panels with a share ring, and a 12-month trend chart with a series
  switcher reading the `months` payload,
* read stats from entities via the `key` attribute (never from guessed entity ids),
* surface **every** sensor key somewhere (the headline number, a chip, the rolling strip, a period
  table row, a last-fill row or the fill-up list); a key the card never renders
  is a bug — `avg_price_per_liter` was exactly that until 0.1.1. The period
  totals are shown through their period: `month_distance`/`month_liters`/
  `month_fill_count` and the `year_*` totals appear as the km/L/fills columns of
  the monthly and yearly tables, and the `rolling_*` values in the summary
  strip. Because a sensor key is not always a literal in the card source, this
  rule stays a review rule; the machine-checked guard covers the period payload
  (`PeriodUsage.as_dict()` keys must all be read by the card),
* list recent fill-ups from the `fillups` attribute of the `last_fill` entity,
* show the current month and the current year (`month_cost`, `month_avg_consumption`,
  `year_cost`, `year_avg_consumption` tiles, each labelled with its `month`/`year`
  attribute), a compact **last 12 months** summary line (the four `rolling_*` values,
  labelled with their `window` attribute) and **two** comparison tables read from the
  `months` attribute of `month_cost` and the `years` attribute of `year_cost`:
  period, km, litres, cost, L/100km and fill-up count, plus the change against
  the previous period (consumption, cost and km). Both tables share one renderer.
  The current period is marked, and a period whose `avg_consumption` is `null`
  shows `-` instead of a fabricated number,
* offer a CSV export action that calls `fuelusagetracker.export_csv` for the
  selected vehicle (scope `fillups`) and reports the written path or the error,
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
