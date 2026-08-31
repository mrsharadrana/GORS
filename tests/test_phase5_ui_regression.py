from pathlib import Path


APP_CANDIDATES = [Path("app.py"), Path("GORS_APP_PROD/app.py")]


def _app_source():
    for path in APP_CANDIDATES:
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise AssertionError("GORS Streamlit app not found")


def test_phase5_ui_requirements_present():
    source = _app_source()
    assert "Last Data Updated" in source
    assert "Rotation History" in source or "rotation history" in source.lower()
    assert "Top 3" in source
    assert "Current Holdings" in source or "holdings" in source.lower()


def test_phase5_has_no_broker_order_execution():
    source = _app_source().lower()
    forbidden = ("place_order(", "modify_order(", "cancel_order(")
    assert not any(token in source for token in forbidden)
