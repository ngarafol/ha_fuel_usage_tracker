"""CSV export of a vehicle's fill-ups, months and years."""

from __future__ import annotations

import csv
import io
import logging
import re
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import EXPORT_SCOPES
from .data import FuelUsage, PeriodUsage

_LOGGER = logging.getLogger(__name__)

#: Excel on Windows only reads UTF-8 correctly with a BOM (Croatian station names).
ENCODING = "utf-8-sig"

FILLUP_COLUMNS = (
    "date",
    "liters",
    "price",
    "price_per_liter",
    "odometer",
    "full",
    "station",
    "notes",
)
PERIOD_COLUMNS = ("period", "distance", "liters", "cost", "avg_consumption", "fill_count")


def build_csv(usage: FuelUsage, scope: str) -> tuple[str, int]:
    """Return the CSV text and row count for one export scope."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    if scope == "fillups":
        writer.writerow(FILLUP_COLUMNS)
        rows = [
            [
                fill.date.isoformat(),
                f"{fill.liters:g}",
                f"{fill.price:.2f}",
                "" if (per_liter := fill.price_per_liter) is None else f"{per_liter:.3f}",
                "" if fill.odometer is None else f"{fill.odometer:g}",
                "yes" if fill.full else "no",
                fill.station or "",
                fill.notes or "",
            ]
            for fill in usage.fillups
        ]
    elif scope in ("months", "years"):
        writer.writerow(PERIOD_COLUMNS)
        periods: list[PeriodUsage] = usage.months() if scope == "months" else usage.years()
        rows = [
            [
                period.key,
                "" if period.distance is None else f"{period.distance:g}",
                f"{period.liters:g}",
                f"{period.cost:.2f}",
                "" if period.avg_consumption is None else f"{period.avg_consumption:g}",
                str(period.fill_count),
            ]
            for period in periods
        ]
    else:
        raise HomeAssistantError(
            f"Unknown export scope '{scope}'; use one of {', '.join(EXPORT_SCOPES)}"
        )
    writer.writerows(rows)
    return buffer.getvalue(), len(rows)


def csv_path(
    hass: HomeAssistant, vehicle: str, scope: str, filename: str | None = None
) -> Path:
    """Resolve the export target inside the Home Assistant config directory.

    Only a plain file name is accepted: anything with a path separator, a parent
    reference or a hidden-file prefix is rejected, so an export cannot escape the
    config directory.
    """
    if filename is not None:
        name = filename.strip()
        if (
            name in {"", ".", ".."}
            or name.startswith(".")
            or any(sep in name for sep in ("/", "\\"))
            or not name.endswith(".csv")
        ):
            raise HomeAssistantError(
                "'filename' must be a plain .csv file name without directories"
            )
    else:
        slug = re.sub(r"[^a-z0-9]+", "_", vehicle.casefold()).strip("_") or "vehicle"
        name = f"fuelusagetracker_{slug}_{scope}.csv"
    return Path(hass.config.path(name))
