import pandas as pd

from gors_engine import calculate_gors_signal


def test_top3_uses_latest_completed_month_end(monkeypatch):
    idx = pd.bdate_range("2025-07-01", "2026-01-30")
    panel = pd.DataFrame({"A": range(len(idx)), "B": range(len(idx), 2*len(idx)), "C": range(2*len(idx), 3*len(idx)), "D": range(3*len(idx), 4*len(idx))}, index=idx)

    monkeypatch.setattr("gors_engine.run_frozen_backtest", lambda panel, as_of=None: {
        "state": pd.DataFrame([{"RiskOn": False, "TargetExposure": 1.0, "ActualExposure": 1.0, "Drawdown": 0.0, "Equity": 100000.0, "Cash": 0.0, "MarketValue": 100000.0}], index=[panel.index[-1]]),
        "events": pd.DataFrame(), "metrics": {}, "trades": 0, "annual_turnover": 0.0
    })

    signal = calculate_gors_signal(panel, as_of=pd.Timestamp("2026-01-31"))
    assert signal["ranking_date"] == "2026-01-30"
    assert signal["signal_date"] == "2026-01-30"
    assert len(signal["top3"]) == 3
