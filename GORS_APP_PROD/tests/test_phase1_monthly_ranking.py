import pandas as pd

from gors_engine import calculate_gors_signal


def _stub_backtest(panel, as_of=None):
    cutoff = panel.index[-1]
    return {
        "state": pd.DataFrame([{
            "RiskOn": False,
            "TargetExposure": 1.0,
            "ActualExposure": 1.0,
            "Drawdown": 0.0,
            "Equity": 100000.0,
            "Cash": 0.0,
            "MarketValue": 100000.0,
        }], index=[cutoff]),
        "events": pd.DataFrame(),
        "metrics": {},
        "trades": 0,
        "annual_turnover": 0.0,
    }


def _panel():
    idx = pd.bdate_range("2025-07-01", "2026-02-27")
    return pd.DataFrame(
        {
            "A": range(1, len(idx) + 1),
            "B": range(101, 101 + len(idx)),
            "C": range(201, 201 + len(idx)),
            "D": range(301, 301 + len(idx)),
        },
        index=idx,
        dtype=float,
    )


def test_top3_uses_latest_completed_month_end(monkeypatch):
    panel = _panel()
    jan_end = panel.index[panel.index.to_period("M") == "2026-01"][-1]
    panel.loc[panel.index > jan_end, "D"] *= 1000
    monkeypatch.setattr("gors_engine.run_frozen_backtest", _stub_backtest)

    # Mid-February: D is now much stronger, but the dashboard must still
    # use the January month-end ranking until the next monthly rebalance.
    signal = calculate_gors_signal(panel.loc[:"2026-02-13"], as_of=pd.Timestamp("2026-02-14"))

    assert signal["signal_date"] == "2026-02-13"
    assert signal["ranking_date"] == "2026-01-30"
    assert signal["top3"] == ["A", "B", "C"]


def test_top3_can_change_at_next_monthly_rebalance(monkeypatch):
    panel = _panel()
    jan_end = panel.index[panel.index.to_period("M") == "2026-01"][-1]
    panel.loc[panel.index > jan_end, "D"] *= 1000
    monkeypatch.setattr("gors_engine.run_frozen_backtest", _stub_backtest)

    signal = calculate_gors_signal(panel, as_of=pd.Timestamp("2026-02-28"))

    assert signal["ranking_date"] == "2026-02-27"
    assert signal["top3"][0] == "D"
    assert len(signal["top3"]) == 3
