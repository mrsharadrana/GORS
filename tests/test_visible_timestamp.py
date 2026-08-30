from pathlib import Path


def test_main_dashboard_exposes_last_market_refresh():
    text = (Path(__file__).resolve().parents[1] / "GORS_APP_PROD/app.py").read_text(encoding="utf-8")
    assert "Last Market Refresh" in text
    assert 'latest_market_refresh[0]["created_at"]' in text
    assert "save_decision(date.today().isoformat()" not in text
