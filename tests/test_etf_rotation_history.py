from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "GORS_APP_PROD/pages/History.py"


def test_history_page_exists_and_reads_decision_history():
    text = PAGE.read_text(encoding="utf-8")
    assert PAGE.exists()
    assert "from gors_db import get_decisions" in text
    assert "get_decisions(limit=1000)" in text


def test_rotation_logic_ignores_order_only_changes():
    text = PAGE.read_text(encoding="utf-8")
    assert "frozenset(current)" in text
    assert "current_set != previous" in text
    assert "Ranking/order changes alone are deliberately ignored" in text


def test_history_shows_rotation_summary():
    text = PAGE.read_text(encoding="utf-8")
    assert "Current Top 3" in text
    assert "Last ETF Change" in text
    assert "Total Rotations" in text
    assert "Previous Top 3" in text
    assert "New Top 3" in text
