from __future__ import annotations

from dataclasses import replace

from gors_engine import ManualAction


def strategy_top3(signal: dict) -> list[str]:
    """Return the engine's ranked Top-3, not the current held positions."""
    state = signal.get("state")
    if state is not None and not state.empty:
        raw = state.iloc[-1].get("Top3", "")
        if isinstance(raw, str) and raw:
            return [x for x in raw.split(";") if x]
    return list(signal.get("top3", []))[:3]


def build_safe_manual_actions(signal: dict, kite_rows: list[dict], cash: float) -> list[ManualAction]:
    """Build manual actions while guaranteeing displayed BUY value never exceeds cash.

    SELL actions are emitted first because their proceeds can fund subsequent BUYs.
    BUY quantities are capped using the remaining available cash after estimated costs.
    """
    from gors_engine import build_manual_actions

    raw_actions = build_manual_actions(signal, kite_rows, cash)
    available = max(float(cash), 0.0)
    safe: list[ManualAction] = []

    # Sells can release cash before buys are executed.
    for action in raw_actions:
        if action.action == "SELL":
            safe.append(action)
            if action.approximate_value:
                available += float(action.approximate_value)

    for action in raw_actions:
        if action.action != "BUY":
            continue
        price = (float(action.approximate_value) / action.quantity) if action.quantity and action.approximate_value else 0.0
        if price <= 0 or available <= 0:
            continue
        qty = min(action.quantity or 0, int(available // price))
        if qty <= 0:
            continue
        value = qty * price
        safe.append(replace(action, quantity=qty, approximate_value=value))
        available -= value

    return safe
