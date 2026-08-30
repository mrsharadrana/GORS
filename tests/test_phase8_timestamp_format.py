from datetime import datetime

from GORS_APP_PROD.app import format_snapshot_time


def test_format_snapshot_time_uses_ist():
    value = "2026-08-30T10:49:47"
    assert format_snapshot_time(value) == "30-Aug-2026 04:19 PM IST"
