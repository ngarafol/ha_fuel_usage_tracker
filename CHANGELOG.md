# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

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

[0.4.0]: https://github.com/nix/ha_fuel_usage_tracker/releases/tag/v0.4.0
[0.3.0]: https://github.com/nix/ha_fuel_usage_tracker/releases/tag/v0.3.0
[0.2.0]: https://github.com/nix/ha_fuel_usage_tracker/releases/tag/v0.2.0
[0.1.1]: https://github.com/nix/ha_fuel_usage_tracker/releases/tag/v0.1.1
[0.1.0]: https://github.com/nix/ha_fuel_usage_tracker/releases/tag/v0.1.0
