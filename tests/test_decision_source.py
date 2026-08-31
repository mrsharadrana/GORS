import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "GORS_APP_PROD"))

import gors_decision
import gors_engine as engine


def sample_panel(days=240):
    idx = pd.bdate_range("2020-01-01", periods=days)
    data = {}
    for i, name in enumerate(engine.TICKERS):
        slope = 0.15 + i * 0.03
        wave = np.sin(np.arange(days) / 5.0) * (0.5 + i * 0.05)
        data[name] = 100 + np.arange(days) * slope + wave
    return pd.DataFrame(data, index=idx)


def risk_panel(days=220, crash_day=150):
    idx = pd.bdate_range("2020-01-01", periods=days)
    values = np.full(days, 100.0)
    values[crash_day:] = 90.0
    return pd.DataFrame({name: values.copy() for name in engine.TICKERS}, index=idx)


def test_shared_decision_returns_exact_engine_top3(monkeypatch):
    panel = sample_panel()
    monkeypatch.setattr(gors_decision, "load_market_data", lambda: panel)

    as_of = panel.index[-1] + pd.Timedelta(days=1)
    decision = gors_decision.get_current_gors_decision(as_of=as_of)
    cutoff = engine.latest_completed_common_date(panel, as_of=as_of)
    scoped = panel.loc[:cutoff]
    expected = engine.calculate_gors_signal(scoped, as_of=cutoff + pd.Timedelta(days=1))

    assert decision["top3"] == expected["top3"]
    assert decision["risk_state"] == expected["risk_state"]
    assert decision["signal_date"] == expected["signal_date"]
    assert decision["ranking_date"] == expected["ranking_date"]
    assert decision["target_exposure_pct"] == pytest.approx(expected["target_exposure_pct"])


def test_top3_validation_requires_exactly_three(monkeypatch):
    panel = sample_panel()
    monkeypatch.setattr(gors_decision, "load_market_data", lambda: panel)
    monkeypatch.setattr(
        gors_decision,
        "calculate_gors_signal",
        lambda panel, as_of: {
            "top3": ["A", "B", "C", "D"],
            "risk_state": "RISK ON",
            "signal_date": "2026-01-01",
            "ranking_date": "2026-01-01",
            "target_exposure_pct": 1.0,
            "current_drawdown": 0.0,
        },
    )

    with pytest.raises(RuntimeError, match="expected exactly 3 Top-3 ETFs"):
        gors_decision.get_current_gors_decision(as_of=panel.index[-1])


def test_shared_decision_rejects_invalid_risk_state(monkeypatch):
    panel = sample_panel()
    monkeypatch.setattr(gors_decision, "load_market_data", lambda: panel)
    monkeypatch.setattr(
        gors_decision,
        "calculate_gors_signal",
        lambda panel, as_of: {
            "top3": ["A", "B", "C"],
            "risk_state": "UNKNOWN",
            "signal_date": "2026-01-01",
            "ranking_date": "2026-01-01",
            "target_exposure_pct": 1.0,
            "current_drawdown": 0.0,
        },
    )

    with pytest.raises(RuntimeError, match="unknown risk state"):
        gors_decision.get_current_gors_decision(as_of=panel.index[-1])


def test_cutoff_changes_risk_state_instead_of_using_full_history():
    panel = risk_panel()
    crash_date = panel.index[150]

    before_crash = gors_decision.get_current_gors_decision(
        panel=panel,
        as_of=crash_date,
    )
    after_crash = gors_decision.get_current_gors_decision(
        panel=panel,
        as_of=crash_date + pd.Timedelta(days=1),
    )

    assert before_crash["signal_date"] == (crash_date - pd.offsets.BDay(1)).date().isoformat()
    assert before_crash["risk_state"] == "RISK ON"
    assert after_crash["signal_date"] == crash_date.date().isoformat()
    assert after_crash["risk_state"] == "RISK OFF"
    assert after_crash["target_exposure_pct"] == pytest.approx(engine.RISK_OFF_EXPOSURE)


def test_timezone_aware_as_of_uses_india_market_calendar():
    panel = risk_panel(days=180, crash_day=999)
    # 20:00 UTC is already the next calendar day in India.
    as_of = pd.Timestamp("2020-08-31T20:00:00+00:00")

    decision = gors_decision.get_current_gors_decision(panel=panel, as_of=as_of)

    assert decision["signal_date"] == "2020-08-31"
