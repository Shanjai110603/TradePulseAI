"""
Tests for Forex Market Hours, Weekend Standby Detection, and Session States.
"""
import datetime
import pytest
from core.ingester.market_hours import get_forex_market_status

def test_forex_market_closed_on_weekend():
    # Saturday at 14:00 UTC -> Market must be closed
    sat_dt = datetime.datetime(2026, 9, 26, 14, 0, 0, tzinfo=datetime.timezone.utc)
    res = get_forex_market_status(sat_dt)
    assert res["is_open"] is False
    assert res["status"] == "WEEKEND_STANDBY"
    assert "reopen" in res["status_desc"].lower()

    # Sunday at 10:00 UTC -> Market must still be closed (opens at 21:00 UTC)
    sun_morning = datetime.datetime(2026, 9, 27, 10, 0, 0, tzinfo=datetime.timezone.utc)
    res_sun = get_forex_market_status(sun_morning)
    assert res_sun["is_open"] is False
    assert res_sun["status"] == "WEEKEND_STANDBY"
    assert res_sun["time_until_reopen"] is not None

def test_forex_market_open_on_weekday():
    # Tuesday at 12:00 UTC -> London / NY overlap -> Market must be open
    tue_dt = datetime.datetime(2026, 9, 29, 12, 0, 0, tzinfo=datetime.timezone.utc)
    res = get_forex_market_status(tue_dt)
    assert res["is_open"] is True
    assert res["status"] == "LIVE_OPEN"
    assert "Live" in res["status_desc"]
