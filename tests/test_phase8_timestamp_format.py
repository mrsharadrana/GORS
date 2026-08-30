from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "GORS_APP_PROD/app.py"


def test_timestamp_format_is_embedded_in_live_app():
    text = PAGE.read_text(encoding="utf-8")
    assert "Asia/Kolkata" in text
    assert "%d-%b-%Y %I:%M %p IST" in text
