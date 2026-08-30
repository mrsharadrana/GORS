from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "GORS_APP_PROD/pages/Rotation_Signal.py"


def test_phase5_page_exists_and_has_mobile_layout():
    text = PAGE.read_text(encoding="utf-8")
    assert "@media(max-width:700px)" in text
    assert "Last Data Updated:" in text
    assert "GORS HR5 Dashboard" in text


def test_phase5_page_keeps_signal_only_boundary():
    text = PAGE.read_text(encoding="utf-8")
    assert "No broker orders" in text
    assert "build_safe_manual_actions" in text
