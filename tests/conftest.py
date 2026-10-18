"""Fixtures shared by the Fuel Usage Tracker tests."""

from __future__ import annotations

from datetime import UTC
from zoneinfo import ZoneInfo

import pytest
from homeassistant.util import dt as dt_util


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load ``custom_components`` for every test."""
    yield


@pytest.fixture
def utc_timezone():
    """Pin the default time zone: `data.py` buckets periods through `dt_util`."""
    previous = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(UTC)
    yield UTC
    dt_util.set_default_time_zone(previous)


@pytest.fixture
def zagreb_timezone():
    """A one-hour-ahead zone, so a late-evening fill-up crosses the period."""
    previous = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(ZoneInfo("Europe/Zagreb"))
    yield ZoneInfo("Europe/Zagreb")
    dt_util.set_default_time_zone(previous)
