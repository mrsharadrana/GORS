"""Production adapter for the authoritative frozen GORS backtest.

The frozen strategy implementation remains gors_final_fixed.py at repository root.
This module deliberately delegates strategy calculations to that source instead of
copying/reimplementing them, so the manual dashboard cannot drift from research.
No broker execution is performed here.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FROZEN_PATH = ROOT / "gors_final_fixed.py"


def _load_frozen():
    if not FROZEN_PATH.exists():
        raise RuntimeError(f"Authoritative frozen engine missing: {FROZEN_PATH}")
    spec = importlib.util.spec_from_file_location("gors_frozen", FROZEN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load authoritative frozen engine")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _panel(frozen):
    raw = frozen.download()
    corrected = {k: v.copy() for k, v in raw.items()}
    for d in ["2021-06-17", "2021-06-18"]:
        ts = pd.Timestamp(d)
        if ts in corrected["MON100"].index:
            corrected["MON100"].loc[ts] *= 10.0
    if not frozen.mon100_audit(raw, corrected):
        raise RuntimeError("MON100 correction gate failed")
    panel = pd.DataFrame(corrected).sort_index()
    panel = panel[~panel.index.duplicated(keep="last")]
    complete = panel.notna().all(axis=1)
    if not complete.any():
        raise RuntimeError("No complete common market-data date")
    last_complete = panel.index[complete][-1]
    return panel.loc[:last_complete].copy(), frozen.first_valid(panel)


def calculate_current_signal() -> dict[str, Any]:
    """Replay the exact frozen HR5 engine through the latest completed date."""
    frozen = _load_frozen()
    panel, start_date = _panel(frozen)
    end_date = panel.index.max()
    eq, trades, turnover, annual_turnover, risk_events, risk_rebalances, state, events = frozen.run_forensic(
        panel, start_date, 0.0025, 5, 0.08, 0.50, 0.75
    )
    latest = state.iloc[-1]
    holdings = []
    raw_holdings = str(latest.get("Holdings") or "")
    for item in raw_holdings.split(";"):
        if not item or ":" not in item:
            continue
        ticker, qty = item.split(":", 1)
        holdings.append({"ETF": ticker, "Quantity": float(qty)})

    top3 = []
    scores = frozen.eligible(panel, end_date)
    for ticker, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]:
        top3.append({"ETF": ticker, "126D Return": float(score), "Held": ticker in {h["ETF"] for h in holdings}})

    metrics = frozen.stats(eq)
    return {
        "signal_date": end_date.date().isoformat(),
        "risk_state": "RISK OFF" if bool(latest["RiskOn"]) else "RISK ON",
        "target_exposure": float(latest["TargetExposure"]),
        "actual_exposure": float(latest["ActualExposure"]),
        "drawdown": float(latest["Drawdown"]),
        "equity": float(latest["Equity"]),
        "cash": float(latest["Cash"]),
        "holdings": holdings,
        "top3": top3,
        "trades": int(trades),
        "annual_turnover": float(annual_turnover),
        "risk_events": int(risk_events),
        "risk_rebalances": int(risk_rebalances),
        "metrics": metrics,
        "events": events.tail(25).to_dict("records"),
        "state": state.tail(30).to_dict("records"),
    }


# Explicit public aliases used by the Streamlit page.
get_current_signal = calculate_current_signal
