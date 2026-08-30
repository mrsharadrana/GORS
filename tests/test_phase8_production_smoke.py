from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "GORS_APP_PROD/app.py"


def test_production_dashboard_safety_boundary():
    text = PAGE.read_text(encoding="utf-8")
    assert "Last Data Updated" in text
    assert "No broker orders" in text or "No broker execution" in text


def test_production_dashboard_exists():
    assert PAGE.exists()


def test_timestamp_is_human_readable_ist():
    text = PAGE.read_text(encoding="utf-8")
    assert "pd.to_datetime(snapshot[\"snapshot_time\"], utc=True)" in text
    assert "Asia/Kolkata" in text
    assert "%d-%b-%Y %I:%M %p IST" in text
