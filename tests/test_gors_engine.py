from datetime import timedelta
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "GORS_APP_PROD"))
import gors_engine as engine
from gors_dashboard_helpers import build_safe_manual_actions, strategy_top3


def sample_panel(days=180, shock=False):
    idx = pd.bdate_range("2020-01-01", periods=days)
    data = {}
    for i, name in enumerate(engine.TICKERS):
        slope = 0.15 + i * 0.03
        wave = np.sin(np.arange(days) / 5.0) * (0.5 + i * 0.05)
        data[name] = 100 + np.arange(days) * slope + wave
    if shock:
        for name in data:
            data[name][-5:] = np.asarray(data[name][-5:]) * 0.70
    return pd.DataFrame(data, index=idx)


def reference_rsi(s, period=14):
    d = s.diff(); g = d.clip(lower=0); l = -d.clip(upper=0)
    ag = g.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    al = l.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    out = 100 - 100 / (1 + ag / al.replace(0, np.nan))
    return out.where(~((al == 0) & (ag > 0)), 100.0)


def test_completed_date_selection_ignores_as_of_day():
    panel = sample_panel(); assert engine.latest_completed_common_date(panel, as_of=panel.index[-1]) == panel.index[-2]


def test_mon100_correction_exact_dates_only():
    idx = pd.to_datetime(["2021-06-17", "2021-06-18", "2021-06-21"])
    raw = {name: pd.Series([10.0, 11.0, 120.0], index=idx) for name in engine.TICKERS}
    corrected = engine.apply_mon100_correction(raw)
    assert corrected["MON100"].loc["2021-06-17"] == 100.0
    assert corrected["MON100"].loc["2021-06-18"] == 110.0
    assert corrected["MON100"].loc["2021-06-21"] == 120.0
    assert engine.mon100_audit(raw, corrected)


def test_rsi_matches_authoritative_formula():
    pd.testing.assert_series_equal(engine.rsi(sample_panel()["SILVER"]), reference_rsi(sample_panel()["SILVER"]))


def test_first_valid_uses_monthly_eligibility():
    panel = sample_panel(); first = engine.first_valid(panel)
    assert first in engine.monthly_dates(panel.index) and len(engine.eligible(panel, first)) >= engine.TOP_N


def test_risk_off_exposure_is_half_when_drawdown_triggered():
    result = engine.run_frozen_backtest(sample_panel(shock=True))
    assert result["state"]["RiskOn"].any() and 0.50 in set(result["state"]["TargetExposure"].round(2))


def test_risk_on_exposure_is_full_when_not_triggered_initially():
    assert engine.run_frozen_backtest(sample_panel())["state"].iloc[0]["TargetExposure"] == 1.0


def test_strategy_top3_comes_from_ranked_state():
    signal = {"top3": ["HELD1", "HELD2", "HELD3"], "state": pd.DataFrame([{"Top3": "A;B;C"}])}
    assert strategy_top3(signal) == ["A", "B", "C"]


def test_safe_actions_never_exceed_cash():
    signal = {"holdings": {"A": 10}, "top3": ["A"], "prices": {"A": 100.0}, "signal_date": "2026-01-01", "risk_state": "RISK ON"}
    safe = build_safe_manual_actions(signal, [], cash=250.0)
    buys = [a for a in safe if a.action == "BUY"]
    assert len(buys) == 1
    assert buys[0].quantity == 2
    assert buys[0].approximate_value == 200.0


def test_hold_action_when_kite_matches_engine_target():
    panel = sample_panel()
    signal = engine.calculate_gors_signal(panel, as_of=panel.index[-1] + timedelta(days=1))
    rows = [{"etf": etf, "quantity": qty, "last_price": signal["prices"][etf], "value": qty * signal["prices"][etf]} for etf, qty in signal["holdings"].items()]
    assert engine.build_manual_actions(signal, rows, cash=signal["cash"]) == []


def test_frozen_reference_metrics_are_explicitly_documented():
    assert engine.REFERENCE_METRICS == {"Final": 350_874.56, "CAGR": 0.2296, "MaxDD": -0.1857, "Sharpe": 1.323, "Trades": 52, "AnnualTurnover": 2.85}
