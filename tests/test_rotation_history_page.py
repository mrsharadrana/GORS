from pathlib import Path


def test_history_page_uses_isolated_rotation_logic():
    text = (Path(__file__).resolve().parents[1] / "GORS_APP_PROD/pages/History.py").read_text(encoding="utf-8")
    assert "from rotation_history import rotation_history, top3" in text
    assert "ETF Membership Changes" in text
