# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [0.13.5] - 2026-11-23

### Fixed

* **One registration per start, and stale resources are cleaned up.** The
  per-start URL (0.13.4) made every restart create a *new* dashboard resource
  while the old one stayed behind and 404'd; Lovelace aborts the whole resource
  load on a failed import, so the element never got defined — "Custom element
  does not exist" and no card in the picker, even though the file was served
  fine (verified: 200, 67 KB, current build). Two vehicles also registered two
  boot URLs concurrently (the guard was set after the first await).
  Now the guard is claimed before any await and the resource is matched by path
  prefix: one entry, updated in place, all stale ones deleted.

## [0.13.4] - 2026-11-23

### Changed

* The card is served under a **path that is new on every Home Assistant start**
  (`/fuelusagetracker/fuelusagetracker-card-<boot>.js`), in addition to the
  stable `/fuelusagetracker/fuelusagetracker-card.js` alias. Query-string cache
  busting could still be answered by a poisoned cache entry (a 304 for the
  module, leaving the element undefined and the card absent from the picker);
  a new path cannot. Verified: both paths return 200 and the file on disk.

## [0.13.3] - 2026-11-23

### Changed

* The card module URL now carries a **boot id** (`?v=0.13.3&b=1a2b3c4d`, new on
  every Home Assistant start) in addition to the version. A browser or
  service-worker cache can therefore never answer the request from an old — or
  broken — entry, which is what kept an old card (or a missing card) alive after
  an update.

## [0.13.2] - 2026-11-23

### Changed

* The card logs its build (`[fuelusagetracker-card] build 0.13.2`) on load, so it
  is obvious in the browser console which file the client actually runs; the
  release script keeps that marker in sync with `manifest.json`.
* Both loading paths (extra frontend module and dashboard resource) use the
  versioned URL again — a fresh query string is the only URL a stale service
  worker or browser cache cannot answer from an old entry.

## [0.13.1] - 2026-11-23

### Fixed

* "Custom element does not exist: fuelusagetracker-card" after an update: the
  card is loaded twice on purpose now. The extra frontend module keeps the
  versioned URL (`?v=…`, busts caches) and the **dashboard resource uses the
  stable, unversioned URL**, so a client that cached a broken response for a
  versioned URL still gets the card from the other path. The file is served
  with no-cache headers, so freshness never depended on the query.

## [0.13.0] - 2026-11-23

### Added

* **History block** under the period cards:
  * four mini sparkline cards — L/100 km, cost, distance and price per litre —
    each with the latest value and its change against the previous month;
  * a **12M / 24M** range switch on the trend chart (the payload already keeps
    24 months), next to the existing L/100 km / cost / distance series switch.

## [0.12.1] - 2026-11-23

### Fixed

* Switching back to another vehicle did not work with more than two in the card:
  the popup picker was clipped by the glow header and fought focus/rebuild, so
  the second click landed on a stale menu. Replaced it with **one chip per
  vehicle** in the header — a tap selects directly, no menu to open, close or
  clip. Verified with three consecutive switches (Toyota → Passat → Toyota).

## [0.12.0] - 2026-11-23

### Added

* **12-month trend chart** under the period cards: an SVG area + line over the
  monthly history, a segmented control to switch between L/100 km, cost and
  distance, and a pointer/tap read-out of the month under the cursor.
* **Bar mini-chart** in the glow header (monthly cost) instead of the line
  sparkline.
* **Share rings** on the *This month* / *This year* panels: the period's cost
  against the usual one, percentage inside the ring. The flat bars they replace
  are gone.

### Changed

* Chips are tighter and show their unit with a small gap; the ring sits in the
  panel head so the value column keeps its full width.

## [0.11.0] - 2026-11-23

### Changed

* **Card redesign — glow, no more boxes.** Following the current Home Assistant
  look (Mushroom chips, frosted glass panels, gradient area charts):
  * a gradient glow header built from the theme's `--primary-color`, with the
    vehicle avatar (the *Car image*, or the vehicle initial), the name and
    fuel/engine line, and the headline average consumption as a big number with
    its **12-month sparkline** and a "vs 12-month" delta pill;
  * one row of glass chips for the other eleven figures (label over value);
  * *This month* / *This year* as frosted panels whose bar shows the period's
    cost against the usual one (12-month average for the month, the trailing
    12 months for the year);
  * the vehicle picker is a pill inside the glow header, and the avatar replaces
    the old photo hero — no full-bleed image any more.
* The card now uses only Home Assistant theme variables plus the accent colour,
  so light and dark mode are both first-class; `backdrop-filter` gives the chips
  and panels their frosted look, with a `prefers-reduced-motion` guard.

### Removed

* The photo hero, the car silhouette and the 16-tile grid they replaced.

## [0.10.3] - 2026-11-22

### Changed

* Ponytail audit cleanup, no behaviour change:
  * removed the dead `.header select` rule and the `select` half of the shared
    input rule (the picker is a button now, no `<select>` is created any more);
  * `_currency()` reads `total_cost` once instead of probing four sensors for
    the same unit, and `_image()` reads the vehicle's own `entity_picture`
    instead of scanning every state in Home Assistant;
  * the card's two near-identical value builders share one part builder;
  * `csv_export` inlines the single-use `excel_hr` constant (and drops the then
    unused `typing.Final` import).


## [0.10.2] - 2026-11-22

### Changed

* The vehicle picker is a real control now — a translucent pill with the current
  vehicle name and a small menu — instead of a native `<select>`, which renders
  its own platform chrome inside a shadow root (it came out huge and white, and
  ignored the theme). It opens on click, closes on outside click or Escape, marks
  the current vehicle, and keeps the "remember the last vehicle" behaviour.

## [0.10.1] - 2026-11-22

### Changed

* The vehicle picker in the hero is a compact themed pill (it used to be a bare
  native select) and the card **remembers the vehicle you picked** — with two
  cars, a reload no longer jumps back to the first one.
* The picker only appears when a vehicle has two or more entries; a single-car
  dashboard stays clean.

### Verified

* Two-vehicle fixture: the picker lists both cars, switching swaps the hero name
  and every figure (Passat 6,45 → Peugeot 8,84 L/100km), no overlap with the hero
  text at 528, 560 and 1250 px, no overflow.

## [0.10.0] - 2026-11-22

### Added

* **Car image** (optional, per vehicle): a URL such as `/local/cars/passat.jpg`
  (file in `config/www`). It is exposed as `entity_picture` on every sensor, so
  Home Assistant also shows it in the more-info dialog, and the card uses it as
  the hero background.
* **New card design** — photo hero instead of a grid of boxes:
  * the car photo fills a 200 px hero with a scrim and text shadow; the vehicle
    name, `diesel · 1.6 HDi · 70 fill-ups` and three headline figures (average
    consumption, cost per 100 km, range on a full tank) sit on top of it;
  * without a photo the hero falls back to a themed gradient with an inline car
    silhouette;
  * the remaining eight figures sit in a borderless wrapping row, and *This
    month* / *This year* became two tinted panels;
  * the rolling strip, both comparison tables, the CSV button, the fill-up form
    and the fill-up log (with the per-fill leg line) are unchanged.

### Fixed

* Unit spacing inside the period panels ("6,69 L/100km", not "6,69L/100km").
* Hero text contrast over bright photos (stronger scrim + text shadow), so a
  white car or a sunny shot stays readable.

## [0.9.0] - 2026-11-22

### Added

* `cost_per_100km` — fuel cost per 100 km of the fuel that was actually burned
  (10,12 €/100 km in the demo data), directly comparable with L/100 km.
* `range_full_tank` — kilometres a full tank lasts at the average consumption.
  Needs the new optional **Tank capacity** field (wizard and reconfigure); the
  value is `tank_liters / avg_consumption * 100` and is unknown without it.
* The fill-up list shows, for every full fill-up that closed a measured leg, a
  third line with that leg's figures — `Leg: 897 km · 60,01 L · 6,69 L/100km ·
  100,15 €` — fed by the new `leg_liters`, `leg_distance`, `leg_cost` and
  `leg_consumption` keys in the fill-up payload (`fillup_rows(50)`). Partial
  fill-ups and the first tank carry no leg keys and render no line.

### Changed

* **Breaking:** the `cost_per_km` sensor is replaced by `cost_per_100km`; the
  card tile follows and `Range (full tank)` is added — 16 tiles, 8 + 8 on wide
  cards, auto-fit below 928 px. Sensor count is 30.

## [0.8.0] - 2026-11-22

### Added

* `consumed_liters` and `consumed_cost` sensors — the fuel that actually left the
  tank (measured legs), as opposed to the purchase totals. The card shows them
  next to the averages.
* Card tiles are now 15 and follow the requested order: averages, consumed
  litres/cost, distance and fill-ups, month, year, and the purchase totals
  (`total_cost`, `total_liters`) at the end.
* Card layout: 8 + 7 on wide cards (≥ 928 px), the readable auto-fit layout below
  that. Verified at 1170/1000/940/900/860/800/760/700/640/528/400 px with zero
  overflowing tiles.

### Fixed

* A long value plus its period stamp (e.g. `1.498,80 € 2026`) no longer paints
  outside its tile: `.stat .value` is a wrapping flex row.
* `consumed_liters`/`consumed_cost` return `0.0` (float) instead of the integer
  `0` when no leg has closed yet, so HA renders `0.0` instead of `0`.

## [0.7.0] - 2026-10-22

### Fixed

* `cost_per_km` counted fuel that was still in the tank. It divided *all* spend
  by the measured distance, so the latest fill-up — bought for the next leg —
  inflated the rate (40 L for 60 € at 10 000 km + 45 L for 70 € at 10 500 km gave
  0.26 €/km instead of 0.14). Each leg now carries the cost of the fuel it
  actually burned (the closing fill-up plus any partial fills) and
  `cost_per_km` is that sum over the leg kilometres. `total_cost`,
  `total_liters` and period `cost` stay purchase-based.

### Changed

* **Breaking:** the `km_since_last_fill` sensor is replaced by
  `distance_to_last_fill` (km driven until the latest fill-up, i.e. the last
  measured tank). With odometers entered only at fill-ups, "km since last fill"
  was permanently 0. The card's tile follows; entity count stays 27.

### Added

* README section *How the numbers are calculated*: tank-to-tank accounting, what
  the first fill-up means (the starting tank: its money counts as spend, not as
  cost of driving), a worked example, and why spend and consumption differ.
* Tests for `cost_per_km` (plain leg 0.14, with a partial 0.17, unknown without a
  measured leg, and a trailing purchase that must not change the rate) and for
  `distance_to_last_fill`.

## [0.6.9] - 2026-10-20

### Added

* README section *Missing card in the companion app*, based on the documented app
  behaviour (home-assistant/iOS#3315): the mobile apps cache the frontend, so the
  fix order is restart, check the dashboard resource, then
  *Companion app → Debugging → Reset frontend cache*.

### Changed

* The dashboard-resource registration logs at info what it did (`Registered …` /
  `Updated …`) and warns with the exact manual URL when Lovelace runs in YAML
  resource mode, so a missing card is diagnosable from the Home Assistant log
  without dev tools.

## [0.6.8] - 2026-10-20

### Fixed

* The card is now **also registered as a Lovelace dashboard resource**, not only
  as an extra frontend module. Dashboards load their resources explicitly, so the
  card now works even when a companion app serves a cached frontend shell that
  lacks the extra-module tag — that was the cause of "Custom element does not
  exist: fuelusagetracker-card" in the app while the browser worked. The resource
  is updated in place on a version bump (no duplicate entries) and YAML resource
  mode is left to the module URL. `lovelace` is a declared dependency now.
* The release script replaces only the version value in `manifest.json` instead
  of round-tripping the JSON, which used to reflow the arrays on every release.

## [0.6.7] - 2026-10-20

### Fixed

* The card module is now registered as `…/fuelusagetracker-card.js?v=<version>`
  instead of a fixed URL. Companion apps and browsers were keeping the previous
  card JS after an update (the extra-module URL never changed), which made the
  7 + 6 grid fix and the readable render errors look like they "did not work" on
  the phone. The static path is unchanged — the query only busts caches, and it
  makes the loaded version visible in the browser/app network panel.

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

[0.13.5]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.13.5
[0.13.4]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.13.4
[0.13.3]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.13.3
[0.13.2]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.13.2
[0.13.1]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.13.1
[0.13.0]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.13.0
[0.12.1]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.12.1
[0.12.0]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.12.0
[0.11.0]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.11.0
[0.10.3]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.10.3
[0.10.2]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.10.2
[0.10.1]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.10.1
[0.10.0]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.10.0
[0.9.0]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.9.0
[0.8.0]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.8.0
[0.7.0]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.7.0
[0.6.9]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.6.9
[0.6.8]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.6.8
[0.6.7]: https://github.com/ngarafol/ha_fuel_usage_tracker/releases/tag/v0.6.7
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
