# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [0.6.6] - 2026-10-20

### Fixed

* The 13 stat tiles now keep a stable layout. On cards at least 620 px wide the
  grid is a fixed seven columns, so the tiles are always split 7 + 6 — whether
  the values are filled in or still unknown. Previously `auto-fit` recomputed the
  column count from the available width, so the same card could reflow to
  6 + 6 + 1 depending on how wide it happened to be. Narrow cards (phones) keep
  the auto-fit layout so the labels stay readable.

## [0.6.5] - 2026-10-20

### Added

* `scripts/release.sh X.Y.Z` — one command that bumps `manifest.json`, commits
  it with the CHANGELOG, creates the annotated tag and pushes both. It refuses
  when the CHANGELOG section is missing or unrelated files are dirty, so the tag
  can no longer disagree with the manifest.
* `.githooks/pre-push` — local guard that blocks pushing a `v*` tag whose commit
  carries a different version; enable once with
  `git config core.hooksPath .githooks`.

### Changed

* README *Releases* section documents the one-command flow and the hook instead
  of the manual tag dance that produced two failed release runs.

## [0.6.3] - 2026-10-20

### Added

* GitHub Release automation (`.github/workflows/release.yml`): pushing a `v*`
  tag creates the GitHub Release with the matching CHANGELOG section as notes.
  The run fails when the tag and `manifest.json` disagree, an existing release is
  never recreated, and tags that predate the workflow can be released from the
  Actions tab (*Release → Run workflow → tag*).
* README *Releases* section documenting the flow.

## [0.6.2] - 2026-10-20

### Fixed

* The fill-up litres field rejected plain two-decimal values. In an HTML number
  input the `step` grid starts at `min`, so `min="0.001"` with `step="0.01"` made
  45.20 a step mismatch — the browser then demanded three decimals and offered
  the nearest valid values. The base is now `0.01` (`min`/`step`), so 45, 45.2 and
  45.25 are all valid; the same fix is in the service form (`services.yaml`).
* The odometer fields used `step="1"` and rejected fractional readings; both now
  use `step="any"` as well, so 128450.5 can be entered.

## [0.6.1] - 2026-10-20

### Fixed

* When rendering throws, the card used to let the exception escape `setConfig`,
  so Home Assistant showed only a bare *Configuration error* — with no text, most
  visibly in the companion apps. The card now catches the exception, renders
  "Fuel Usage Tracker could not render this card." with the exception message,
  and logs the full stack to the console under `[fuelusagetracker-card]`, so the
  real cause is visible on the phone as well.

## [0.6.0] - 2026-10-19

### Added

* Native **Reconfigure** wizard: the integration entry's ⋮ menu offers
  *Reconfigure*, which re-runs the add-vehicle wizard prefilled with the current
  name, fuel type, engine and baseline odometer. Saving updates the entry data
  and the vehicle name (the device name and the `vehicle_name` attribute follow
  it; existing entity ids keep their original slugs, because Home Assistant
  generates them only once), strips the vehicle keys from `entry.options`, and
  reloads the entry — cleared optional fields are stored as absent, not as empty
  strings.

### Removed

* The options flow (*Configure*). It showed the same four fields as the wizard
  but wrote into `entry.options`, which `vehicle_settings()` merges after
  `entry.data` — so it silently shadowed the setup data. `Reconfigure` replaces
  it and, on the first save, migrates values an existing install had saved there.

### Tests

* 89 (was 81): the reconfigure flow, including the options-shadowing regression
  guard, blank/duplicate names, cleared optional fields, and the fact that the
  options flow is gone (with its translation block).

## [0.5.1] - 2026-10-19

Second complexity audit applied (ponytail-audit) — no behaviour, entity id,
unique id, unit or attribute changed; 81 tests (was 80) pin exactly that.

### Changed

* `entity.py` is gone: its base class now lives in `sensor.py`, its only
  consumer, and was then merged into `FuelUsageSensor` itself (one consumer does
  not need a class hierarchy).
* `sensor.py`: the separate `unit_template` field is gone (currency templates
  live in `native_unit_of_measurement` and are always formatted), and the
  three-branch period-attribute chain became one `period_kind` map.
* `data.py`: `current_month` / `current_year` share one `_current()` lookup.
* The card's yearly table lost its "Show all" toggle: the `years` payload is
  capped at 10 rows (`YEAR_HISTORY_YEARS`), so the button was unreachable.
* `tests/`: the "27 sensors exist" contract has one owner (`test_setup.py`); the
  duplicate in `test_monthly.py` is gone, and two new guards cover rendered units
  and unique ids, which the refactors above would otherwise have changed silently.
* Repo hygiene: the generated `docs/preview/{monthly-chart,yearly-chart,architecture}.html`
  pages are no longer committed (the PNGs are the artifact), and the `.gitignore`
  entry for a ruff cache no tooling creates is gone.

### Rejected

* Inlining `_async_get_coordinator`: `ConfigEntry.runtime_data` is *deleted* on
  unload (`homeassistant/config_entries.py`), so reading it defensively keeps a
  clear `HomeAssistantError` instead of an `AttributeError` in a service call
  that races an unload. The helper body was tightened instead.

## [0.5.0] - 2026-10-18

### Added

* The card shows the current year as tiles ("This year" cost and consumption),
  next to the existing month tiles.
* `export_csv` gained `format`: `standard` (comma separated, dot decimals, LF —
  unchanged default) and `excel_hr` (semicolon separated, comma decimals, CRLF),
  which is what Excel expects in a Croatian/European locale.
* README recipe for a scheduled export (automation trigger + `notify` target),
  including a templated file name; scheduling itself stays a Home Assistant
  automation concern.

## [0.4.0] - 2026-10-18

### Added

* **Rolling 12-month overview:** `rolling_distance`, `rolling_liters`,
  `rolling_cost` and `rolling_avg_consumption` cover the trailing 12 calendar
  months ending today (never resets on 1 January); the `window` attribute carries
  the exact range.
* **Yearly statistics:** `year_distance`, `year_liters`, `year_cost` and
  `year_avg_consumption` for the current calendar year, plus a year-on-year
  history (`years` attribute on `year_cost`, 10 years).
* **CSV export:** the `export_csv` service writes the fill-up log or the monthly
  or yearly aggregation into the Home Assistant config directory (UTF-8 with BOM)
  and returns `{path, rows}`; the card has an Export CSV button.
* Yearly comparison chart in the previews and a yearly comparison table in the
  card (monthly and yearly tables share one renderer).

### Changed

* `MonthlyUsage` was generalized to `PeriodUsage` with one aggregation for
  months, years and rolling windows; the period payload rows use `period`
  (previously `month`) with the keys `period`, `distance`, `liters`, `cost`,
  `avg_consumption`, `fill_count`.
* Sensors per vehicle: 19 → 27.

## [0.3.0] - 2026-10-18

Complexity audit (ponytail-audit) applied — nothing was removed that had a
consumer, and no behaviour changed except the two removals listed below.

### Removed

* **Breaking:** the `fuelusagetracker.update_fillup` service (schema, handler and
  the matching store/coordinator update paths). Nothing called it: not the card,
  not the docs examples, not the tests. Correct a fill-up by deleting it and
  recording it again.
* The per-leg consumption chart preview (`docs/preview/consumption-chart.html`,
  `docs/images/consumption-chart.png`); the monthly chart covers the same data.
* `MonthlyUsage.avg_price_per_liter` and `cost_per_km` from the `months`
  payload (never rendered by the card), `MonthlyUsage.last_date` (written, never
  read) and `FuelUsage.first_odometer` (no caller).

### Changed

* `sensor.py`: every description now carries its own `value_fn` (plus
  `unit_template`/`monthly` flags) instead of three module-level tables keyed by
  the same 19 keys — the description tuple is the single source of truth.
* The card implements "Show all" once for both lists (was written twice).
* The tests share one `fill()` fixture builder (was written twice).
* Dependencies and defaults: the frontend runtime guard that the manifest
  dependency already guarantees is gone, together with an empty `requirements`
  list, `zip_release: false`, the pytest loop-scope default and speculative
  `.gitignore` entries.

## [0.2.0] - 2026-10-18

### Added

* Monthly statistics per vehicle: kilometres (from the tank-to-tank legs closed
  in that month), litres and cost purchased, average consumption, average price
  per litre, cost per km and the fill-up count. Five `*_this_month` sensors plus
  a 24-month `months` history attribute on the cost sensor.
* The card shows the current month and a monthly comparison table with the
  change against the previous month (km, cost, L/100 km).
* README section on monthly statistics, including the native `utility_meter`
  recipe for Home Assistant's own monthly statistics entities, and a monthly
  comparison chart in the previews.

### Changed

* Sensors per vehicle: 14 → 19.
* The card labels the current-month tiles with the same localized month format
  as the comparison table (previously the raw `2026-10` key).
* The preview diagrams are now drawn from the integration's own aggregation code
  (no second implementation of the maths) and use Croatian number formatting.

### Fixed

* Missing `entity.sensor.month_*.name` translations produced meaningless entity
  ids for the new sensors (`…_2`, `…_monetary_balance`, `…_distance`). English
  and Croatian names added; a test now fails whenever a sensor key has no
  translated name.

## [0.1.1] - 2026-10-18

### Added

* Visual previews in the README, rendered from real sensor states: the card in
  light and dark theme, a consumption/price/cost chart and a data-flow diagram,
  all reproducible from `docs/preview/`.

### Fixed

* The card omitted the average price per litre — `avg_price_per_liter` was the
  only sensor key that no tile, row or list rendered. It is now the fourth stat
  tile (`1,587 EUR/L`). The contract in `docs/ARCHITECTURE.md` now requires the
  card to surface every sensor key.

## [0.1.0] - 2026-10-18

### Added

* `fuelusagetracker` integration with UI config flow for adding vehicles
  (name, fuel type, engine, optional baseline odometer); one config entry is one
  vehicle and one device.
* Fill-up recording through services: `add_fillup`, `update_fillup`,
  `delete_fillup`, `update_vehicle`, including optional odometer, full-tank
  flag, station, notes and date.
* Consumption maths between full-tank fill-ups with odometer readings
  (L/100 km average and last leg, cost per km), odometer and distance tracking.
* 14 sensors per vehicle, prefixed `sensor.fuelusagetracker_*`, with
  `total_increasing` statistics for cost, litres, distance and odometer.
* Bundled Lovelace card `fuelusagetracker-card`, auto-registered as a frontend
  resource: statistics, fill-up form, odometer update and a fill-up list with
  confirmed deletion.
* English and Croatian translations.
* HA integration test suite (config flow, options flow, services, sensor states,
  consumption maths, storage round trip, translation parity).

[0.6.6]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.6.6
[0.6.5]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.6.5
[0.6.3]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.6.3
[0.6.2]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.6.2
[0.6.1]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.6.1
[0.6.0]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.6.0
[0.5.1]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.5.1
[0.5.0]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.5.0
[0.4.0]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.4.0
[0.3.0]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.3.0
[0.2.0]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.2.0
[0.1.1]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.1.1
[0.1.0]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.1.0
