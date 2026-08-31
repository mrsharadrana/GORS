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


def test_shared_decision_returns_exact_engine_top3(monkeypatch):
    panel = sample_panel()
    monkeypatch.setattr(gors_decision, "load_market_data", lambda: panel)

    decision = gors_decision.get_current_gors_decision(as_of=panel.index[-1] + pd.Timedelta(days=1))
    expected = engine.calculate_gors_signal(panel, as_of=panel.index[-1] + pd.Timedelta(days=1))

    assert decision["top3"] == expected["top3"][:3]
    assert decision["risk_state"] == expected["risk_state"]
    assert decision["signal_date"] == expected["signal_date"]
    assert decision["ranking_date"] == expected["ranking_date"]
    assert decision["target_exposure_pct"] == pytest.approx(expected["target_exposure_pct"])


def test_shared_decision_rejects_invalid_top3(monkeypatch):
    panel = sample_panel()

    monkeypatch.setattr(
        gors_decision,
        "load_market_data",
        lambda: panel,
    )
    monkeypatch.setattr(
        gors_decision,
        "calculate_gors_signal",
        lambda panel, as_of: {
            "top3": ["ONLY_ONE"],
            "risk_state": "RISK ON",
            "signal_date": "2026-01-01",
            "ranking_date": "2026-01-01",
            "target_exposure_pct": 1.0,
            "current_drawdown": 0.0,
        },
    )

    with pytest.raises(RuntimeError, match="expected 3 Top-3 ETFs"):
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
