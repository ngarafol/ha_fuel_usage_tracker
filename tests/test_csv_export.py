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
import voluptuous as vol
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
OCTOBER_1 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
OCTOBER_2 = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)

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


def excel_usage() -> FuelUsage:
    """One fill-up whose money fields exercise both decimal separators."""
    return FuelUsage(
        fillups=[
            fill(
                45.2,
                10000.0,
                price=66.44,
                date=JANUARY,
                fillup_id="f1",
                station="INA;Zagreb",
                notes="ok",
            )
        ]
    )


def big_odometer_usage() -> FuelUsage:
    """One fill-up with large fractional litres, odometer and money fields."""
    return FuelUsage(
        fillups=[
            fill(
                45.2,
                1234567.5,
                price=66.44,
                date=JANUARY,
                fillup_id="f1",
                station="INA;Zagreb",
            )
        ]
    )


def month_usage() -> FuelUsage:
    """Two full fills in October: fractional distance, litres and average."""
    return FuelUsage(
        fillups=[
            fill(45.2, 10000.0, price=60.0, date=OCTOBER_1, fillup_id="a"),
            fill(41.0, 10032.5, price=66.44, date=OCTOBER_2, fillup_id="b"),
        ]
    )


def rows_of(text: str, delimiter: str = ",") -> list[list[str]]:
    return list(csv.reader(io.StringIO(text), delimiter=delimiter))


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


def test_standard_format_is_byte_for_byte_unchanged():
    """The pre-`format` output, frozen: comma, dot decimal, LF, trailing newline."""
    text, rows = build_csv(excel_usage(), "fillups")

    assert rows == 1
    assert text == (
        "date,liters,price,price_per_liter,odometer,full,station,notes\n"
        "2026-01-10T09:00:00+00:00,45.2,66.44,1.470,10000,yes,INA;Zagreb,ok\n"
    )


def test_excel_hr_separates_fields_with_semicolons_and_uses_crlf():
    text, rows = build_csv(excel_usage(), "fillups", fmt="excel_hr")

    assert rows == 1
    assert text.startswith("date;liters;price;price_per_liter;odometer;full;station;notes\r\n")
    assert all(line.endswith("\r\n") for line in text.splitlines(keepends=True))
    assert text.replace("\r\n", "").count("\n") == 0


def test_excel_hr_writes_money_with_a_comma_decimal():
    text, _ = build_csv(excel_usage(), "fillups", fmt="excel_hr")

    row = rows_of(text, delimiter=";")[1]

    assert row[2] == "66,44"
    assert row[3] == "1,470"


def test_fillup_numerics_follow_the_format_decimal_separator():
    standard, _ = build_csv(big_odometer_usage(), "fillups")
    excel, _ = build_csv(big_odometer_usage(), "fillups", fmt="excel_hr")

    excel_row = rows_of(excel, delimiter=";")[1]

    assert rows_of(standard)[1][1:5] == ["45.2", "66.44", "1.470", "1234567.5"]
    assert excel_row == [
        "2026-01-10T09:00:00+00:00",
        "45,2",
        "66,44",
        "1,470",
        "1234567,5",
        "yes",
        "INA;Zagreb",
        "",
    ]
    assert all("." not in cell for cell in excel_row[1:5])


def test_month_numerics_follow_the_format_decimal_separator(utc_timezone):
    standard, _ = build_csv(month_usage(), "months")
    excel, _ = build_csv(month_usage(), "months", fmt="excel_hr")

    excel_row = rows_of(excel, delimiter=";")[1]

    assert rows_of(standard)[1] == ["2026-10", "32.5", "86.2", "126.44", "126.15", "2"]
    assert excel_row == ["2026-10", "32,5", "86,2", "126,44", "126,15", "2"]
    assert all("." not in cell for cell in excel_row[1:])


def test_a_large_fractional_odometer_never_uses_scientific_notation():
    """`:g` used to print 1234567.5 as 1.23457e+06 in both formats."""
    standard, _ = build_csv(big_odometer_usage(), "fillups")
    excel, _ = build_csv(big_odometer_usage(), "fillups", fmt="excel_hr")

    assert rows_of(standard)[1][4] == "1234567.5"
    assert rows_of(excel, delimiter=";")[1][4] == "1234567,5"
    assert "e+" not in standard.lower()
    assert "e+" not in excel.lower()


def test_excel_hr_quotes_a_station_containing_the_semicolon_delimiter():
    text, _ = build_csv(excel_usage(), "fillups", fmt="excel_hr")

    assert '"INA;Zagreb"' in text.splitlines()[1]


def test_a_comma_in_a_station_is_quoted_only_in_the_standard_format():
    standard, _ = build_csv(csv_usage(), "fillups")
    excel, _ = build_csv(csv_usage(), "fillups", fmt="excel_hr")

    assert '"INA, Zagreb"' in standard.splitlines()[1]
    assert "INA, Zagreb;" in excel.splitlines()[1]
    assert '"INA, Zagreb"' not in excel.splitlines()[1]


def test_excel_hr_month_rows_use_semicolons_and_a_comma_cost(utc_timezone):
    text, rows = build_csv(csv_usage(), "months", fmt="excel_hr")

    parsed = rows_of(text, delimiter=";")

    assert parsed[0] == list(PERIOD_COLUMNS)
    assert rows == 2
    assert [row[0] for row in parsed[1:]] == ["2026-02", "2026-01"]
    assert parsed[1][3] == "45,00"
    assert text.replace("\r\n", "").count("\n") == 0


def test_excel_hr_year_rows_use_semicolons_and_a_comma_cost(utc_timezone):
    text, rows = build_csv(excel_usage(), "years", fmt="excel_hr")

    parsed = rows_of(text, delimiter=";")

    assert parsed[0] == list(PERIOD_COLUMNS)
    assert rows == 1
    assert parsed[1][0] == "2026"
    assert parsed[1][3] == "66,44"
    assert all(line.endswith("\r\n") for line in text.splitlines(keepends=True))


def test_unknown_format_raises():
    with pytest.raises(HomeAssistantError):
        build_csv(csv_usage(), "fillups", fmt="bogus")


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


async def test_export_csv_service_rejects_an_unknown_format(hass, exported_csv_files):
    entry = await setup_vehicle(hass)

    with pytest.raises((vol.Invalid, HomeAssistantError)):
        await export_csv(
            hass,
            {
                const.CONF_VEHICLE: entry.entry_id,
                const.CONF_SCOPE: "fillups",
                const.CONF_FORMAT: "bogus",
            },
        )

    config_dir = Path(hass.config.config_dir)
    assert set(config_dir.rglob("*.csv")) == exported_csv_files


async def test_export_csv_service_writes_the_excel_hr_format(hass, exported_csv_files):
    entry = await setup_vehicle(hass)
    await add_fillup(
        hass, entry.entry_id, 45.2, 66.44, odometer=BASE_ODOMETER, date=JANUARY.isoformat()
    )

    response = await export_csv(
        hass,
        {
            const.CONF_VEHICLE: entry.entry_id,
            const.CONF_SCOPE: "fillups",
            const.CONF_FORMAT: "excel_hr",
        },
    )

    expected_text, expected_rows = build_csv(entry.runtime_data.data, "fillups", "excel_hr")
    content = Path(response["path"]).read_bytes()

    assert set(response) == {"path", "rows"}
    assert response["rows"] == expected_rows == 1
    assert expected_text.startswith("date;liters;price;")
    assert content.startswith(codecs.BOM_UTF8)
    assert content.decode(ENCODING) == expected_text


async def test_export_csv_defaults_to_the_standard_format(hass, exported_csv_files):
    entry = await setup_vehicle(hass)
    await add_fillup(
        hass, entry.entry_id, 40, 60.0, odometer=BASE_ODOMETER, date=JANUARY.isoformat()
    )

    response = await export_csv(
        hass, {const.CONF_VEHICLE: entry.entry_id, const.CONF_SCOPE: "fillups"}
    )

    content = Path(response["path"]).read_bytes().decode(ENCODING)

    assert content == build_csv(entry.runtime_data.data, "fillups", "standard")[0]
    assert content.startswith("date,liters,price,price_per_liter,odometer,full,station,notes\n")
    assert "\r\n" not in content
