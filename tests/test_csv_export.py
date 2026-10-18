"""CSV export: the built payload, the ``export_csv`` service and path safety.

Contract: ``docs/ARCHITECTURE.md`` "Services" plus ``csv_export.py``.
"""

from __future__ import annotations

import codecs
import csv
import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.fuelusagetracker import const
from custom_components.fuelusagetracker.csv_export import (
    ENCODING,
    FILLUP_COLUMNS,
    PERIOD_COLUMNS,
    build_csv,
)
from custom_components.fuelusagetracker.data import FuelUsage
from tests.helpers import BASE_ODOMETER, add_fillup, fill, setup_vehicle

JANUARY = datetime(2026, 1, 10, 9, 0, tzinfo=UTC)
FEBRUARY = datetime(2026, 2, 10, 9, 0, tzinfo=UTC)

#: A name that is a path, a parent reference, hidden, or not a .csv file.
UNSAFE_FILENAMES = ("../evil.csv", "sub/evil.csv", "..\\evil.csv", ".hidden.csv", "evil.txt", "")


def csv_usage() -> FuelUsage:
    """Two fill-ups: one with CSV metacharacters, one plain partial fill."""
    return FuelUsage(
        fillups=[
            fill(
                40.5,
                10000.0,
                price=60.0,
                date=JANUARY,
                fillup_id="f1",
                station="INA, Zagreb",
                notes='said "hi"',
            ),
            fill(30.0, 10500.0, full=False, date=FEBRUARY, fillup_id="f2", station="OMV"),
        ]
    )


def rows_of(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


async def export_csv(hass, data: dict) -> dict:
    """Call the export service and return its response."""
    return await hass.services.async_call(
        const.DOMAIN, const.SERVICE_EXPORT_CSV, data, blocking=True, return_response=True
    )


def test_fillup_export_has_the_header_and_one_row_per_fillup():
    text, rows = build_csv(csv_usage(), "fillups")

    parsed = rows_of(text)

    assert parsed[0] == list(FILLUP_COLUMNS)
    assert rows == 2
    assert len(parsed) == 3


def test_fillup_row_carries_every_contracted_field():
    text, _ = build_csv(csv_usage(), "fillups")

    row = rows_of(text)[1]

    assert row[0] == "2026-01-10T09:00:00+00:00"
    assert row[1] == "40.5"
    assert row[2] == "60.00"
    assert row[3] == "1.481"
    assert row[4] == "10000"
    assert row[5] == "yes"
    assert row[6] == "INA, Zagreb"
    assert row[7] == 'said "hi"'
    assert rows_of(text)[2][5] == "no"


def test_station_and_notes_with_csv_metacharacters_are_quoted():
    text, _ = build_csv(csv_usage(), "fillups")

    line = text.splitlines()[1]

    assert '"INA, Zagreb"' in line
    assert '"said ""hi"""' in line


def test_month_export_lists_months_newest_first(utc_timezone):
    text, rows = build_csv(csv_usage(), "months")

    parsed = rows_of(text)

    assert parsed[0] == list(PERIOD_COLUMNS)
    assert rows == 2
    assert [row[0] for row in parsed[1:]] == ["2026-02", "2026-01"]


def test_year_export_lists_years_newest_first(utc_timezone):
    usage = FuelUsage(
        fillups=[
            fill(40, 10000.0, date=datetime(2025, 6, 1, 9, 0, tzinfo=UTC), fillup_id="a"),
            fill(45, 10500.0, date=datetime(2026, 6, 1, 9, 0, tzinfo=UTC), fillup_id="b"),
        ]
    )

    text, rows = build_csv(usage, "years")

    parsed = rows_of(text)

    assert parsed[0] == list(PERIOD_COLUMNS)
    assert rows == 2
    assert [row[0] for row in parsed[1:]] == ["2026", "2025"]


def test_unknown_scope_raises():
    with pytest.raises(HomeAssistantError):
        build_csv(csv_usage(), "bogus")


@pytest.fixture
def exported_csv_files(hass):
    """Snapshot HA's config dir; remove the CSVs the test writes.

    The testing config directory is shared and persists between runs, so the
    snapshot is what "created no file" must be measured against, and the
    teardown keeps it from poisoning the next run.
    """
    config_dir = Path(hass.config.config_dir)
    before = set(config_dir.rglob("*.csv"))
    yield before
    for created in set(config_dir.rglob("*.csv")) - before:
        created.unlink()


async def test_export_csv_writes_the_file_and_returns_path_and_rows(
    hass, exported_csv_files
):
    entry = await setup_vehicle(hass)
    await add_fillup(
        hass, entry.entry_id, 40, 60.0, odometer=BASE_ODOMETER, date=JANUARY.isoformat()
    )

    response = await export_csv(
        hass, {const.CONF_VEHICLE: entry.entry_id, const.CONF_SCOPE: "fillups"}
    )

    expected_text, expected_rows = build_csv(entry.runtime_data.data, "fillups")
    written = Path(response["path"])

    assert set(response) == {"path", "rows"}
    assert response["rows"] == expected_rows == 1
    assert written.parent == Path(hass.config.config_dir)
    assert written.name == "fuelusagetracker_premcar_fillups.csv"
    content = written.read_bytes()
    assert content.startswith(codecs.BOM_UTF8)
    assert content.decode(ENCODING) == expected_text


@pytest.mark.parametrize("filename", UNSAFE_FILENAMES)
async def test_export_csv_rejects_unsafe_filenames(hass, exported_csv_files, filename):
    entry = await setup_vehicle(hass)

    with pytest.raises(HomeAssistantError):
        await export_csv(
            hass,
            {
                const.CONF_VEHICLE: entry.entry_id,
                const.CONF_SCOPE: "fillups",
                const.CONF_FILENAME: filename,
            },
        )

    config_dir = Path(hass.config.config_dir)
    assert set(config_dir.rglob("*.csv")) == exported_csv_files
    assert not (config_dir.parent / "evil.csv").exists()


async def test_export_csv_accepts_a_plain_custom_name(hass, exported_csv_files):
    entry = await setup_vehicle(hass)

    response = await export_csv(
        hass,
        {
            const.CONF_VEHICLE: entry.entry_id,
            const.CONF_SCOPE: "fillups",
            const.CONF_FILENAME: "moj_izvoz.csv",
        },
    )

    written = Path(response["path"])

    assert written.name == "moj_izvoz.csv"
    assert written.parent == Path(hass.config.config_dir)


async def test_export_csv_unknown_vehicle_raises(hass):
    await setup_vehicle(hass)

    with pytest.raises(HomeAssistantError):
        await export_csv(
            hass, {const.CONF_VEHICLE: "Ghost", const.CONF_SCOPE: "fillups"}
        )
