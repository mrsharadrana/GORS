from pathlib import Path


def test_main_dashboard_exposes_last_data_updated():
    text = (Path(__file__).resolve().parents[1] / "GORS_APP_PROD/app.py").read_text(encoding="utf-8")
    assert "Last Data Updated" in text
    assert 'snapshot["snapshot_time"]' in text
