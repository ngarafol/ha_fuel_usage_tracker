# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

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

[0.1.0]: https://github.com/nix/ha_fuel_usage_tracker/releases/tag/v0.1.0
