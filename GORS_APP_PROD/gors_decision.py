"""Single source of truth for the live GORS strategy decision."""
from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from cutoff_safe_backtest import run as run_cutoff_safe_backtest
from cutoff_safe_backtest import latest_completed_date
from gors_engine import calculate_gors_signal, load_market_data
INDIA_TZ = ZoneInfo("Asia/Kolkata")

def _normalize_as_of(as_of):
    if as_of is None:
        return datetime.now(INDIA_TZ).replace(tzinfo=None)
    timestamp = pd.Timestamp(as_of)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(INDIA_TZ).tz_localize(None)
    return timestamp.to_pydatetime()

def get_current_gors_decision(*, as_of=None, panel=None) -> dict:
    """Return the frozen GORS decision using the cutoff-safe production path."""
    market_data = load_market_data() if panel is None else panel
    effective_as_of = _normalize_as_of(as_of)
    cutoff = latest_completed_date(market_data, as_of=effective_as_of)
    scoped_panel = market_data.loc[market_data.index <= cutoff].copy()
    signal = calculate_gors_signal(scoped_panel, as_of=cutoff + pd.Timedelta(days=1))
    safe_result = run_cutoff_safe_backtest(scoped_panel, as_of=cutoff + pd.Timedelta(days=1))
    last = safe_result["state"].iloc[-1]
    raw_top3 = list(signal.get("top3", []))
    if len(raw_top3) != 3:
        raise RuntimeError(f"GORS decision is invalid: expected exactly 3 Top-3 ETFs, got {raw_top3}")
    risk_state = "RISK OFF" if bool(last["RiskOn"]) else "RISK ON"
    signal["cutoff"] = cutoff.date().isoformat()
    signal["risk_state"] = risk_state
    signal["target_exposure_pct"] = float(last["TargetExposure"])
    signal["actual_exposure_pct"] = float(last["ActualExposure"])
    signal["current_drawdown"] = float(last["Drawdown"])
    signal["equity"] = float(last["Equity"])
    signal["cash"] = float(last["Cash"])
    signal["market_value"] = float(last["MarketValue"])
    signal["state"] = safe_result["state"]
    signal["events"] = safe_result["events"]
    signal["metrics"] = safe_result["metrics"]
    return {"signal": signal, "signal_date": signal["signal_date"], "ranking_date": signal["ranking_date"], "risk_state": risk_state, "top3": raw_top3, "target_exposure_pct": float(last["TargetExposure"]), "current_drawdown": float(last["Drawdown"])}

def decision_top3(decision: dict) -> list[str]:
    return list(decision["top3"])
