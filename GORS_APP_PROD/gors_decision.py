"""Single source of truth for the live GORS strategy decision.

All dashboard surfaces must consume this service instead of implementing their
own Top-3 or risk-state selection logic. Strategy parameters remain frozen in
``gors_engine``; this module only exposes the engine decision consistently.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from gors_engine import (
    calculate_gors_signal,
    latest_completed_common_date,
    load_market_data,
)

INDIA_TZ = ZoneInfo("Asia/Kolkata")


def _normalize_as_of(as_of):
    """Normalize an as_of timestamp to an India-market calendar timestamp."""
    if as_of is None:
        return datetime.now(INDIA_TZ).replace(tzinfo=None)

    timestamp = pd.Timestamp(as_of)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(INDIA_TZ).tz_localize(None)
    return timestamp.to_pydatetime()


def get_current_gors_decision(*, as_of=None, panel=None) -> dict:
    """Return the current frozen GORS decision from the production engine.

    ``panel`` is injectable for deterministic tests. Production callers should
    omit it so the engine loads the configured market-data source.

    The engine's signal calculation is scoped to the latest completed market
    date first. This prevents a full-history backtest state from leaking into a
    historical/live cutoff decision when ``calculate_gors_signal`` is called
    with an ``as_of`` value.
    """
    market_data = load_market_data() if panel is None else panel
    effective_as_of = _normalize_as_of(as_of)
    cutoff = latest_completed_common_date(market_data, as_of=effective_as_of)
    if cutoff is None:
        raise RuntimeError("GORS decision is invalid: no completed market-data date")

    scoped_panel = market_data.loc[market_data.index <= cutoff].copy()
    # calculate_gors_signal interprets as_of as a boundary strictly after the
    # desired market date, so use the following calendar day to retain cutoff.
    signal = calculate_gors_signal(scoped_panel, as_of=cutoff + pd.Timedelta(days=1))

    raw_top3 = list(signal.get("top3", []))
    if len(raw_top3) != 3:
        raise RuntimeError(
            f"GORS decision is invalid: expected exactly 3 Top-3 ETFs, got {raw_top3}"
        )
    top3 = raw_top3

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
