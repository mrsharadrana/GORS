"""Single source of truth for the live GORS strategy decision.

All dashboard surfaces must consume this service instead of implementing their
own Top-3 or risk-state selection logic. Strategy parameters remain frozen in
``gors_engine``; this module only exposes the engine decision consistently.
"""
from __future__ import annotations

from datetime import datetime

from gors_engine import calculate_gors_signal, load_market_data


def get_current_gors_decision(*, as_of=None, panel=None) -> dict:
    """Return the current frozen GORS decision from the production engine.

    ``panel`` is injectable for deterministic tests. Production callers should
    omit it so the engine loads the configured market-data source.
    """
    market_data = load_market_data() if panel is None else panel
    effective_as_of = datetime.now() if as_of is None else as_of
    signal = calculate_gors_signal(market_data, as_of=effective_as_of)

    top3 = list(signal.get("top3", []))[:3]
    if len(top3) != 3:
        raise RuntimeError(f"GORS decision is invalid: expected 3 Top-3 ETFs, got {top3}")

    risk_state = str(signal.get("risk_state", "")).strip().upper()
    if risk_state not in {"RISK ON", "RISK OFF"}:
        raise RuntimeError(f"GORS decision is invalid: unknown risk state {risk_state!r}")

    return {
        "signal": signal,
        "signal_date": signal["signal_date"],
        "ranking_date": signal["ranking_date"],
        "risk_state": risk_state,
        "top3": top3,
        "target_exposure_pct": float(signal["target_exposure_pct"]),
        "current_drawdown": float(signal["current_drawdown"]),
    }


def decision_top3(decision: dict) -> list[str]:
    """Return the canonical Top-3 from a decision object."""
    return list(decision["top3"])
