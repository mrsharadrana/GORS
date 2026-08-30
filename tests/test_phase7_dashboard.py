from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "GORS_APP_PROD/pages/Rotation_Signal.py"


def test_dashboard_contains_decision_quality_panels():
    text = PAGE.read_text(encoding="utf-8")
    for label in ("Today's Decision", "Top 3 Ranking", "Portfolio Drift", "Risk Control", "Data Health", "Rotation History"):
        assert label in text


def test_dashboard_exposes_frozen_controls_without_changing_engine():
    text = PAGE.read_text(encoding="utf-8")
    for label in ("HoldRank", "DD", "Risk-off", "Recovery", "RSI"):
        assert label in text
    assert "No broker orders" in text
