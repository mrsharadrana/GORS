from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from gors_db import get_decisions, latest_kite_snapshot
from gors_dashboard_helpers import build_safe_manual_actions, strategy_top3
from gors_engine import (
    DD_TRIGGER, HOLD_RANK, RECOVERY_FRACTION, RISK_OFF_EXPOSURE,
    RSI_FULL_EXIT, RSI_EXIT, PRODUCTION_COST, build_holdings_table,
    calculate_gors_signal, load_market_data,
)

st.set_page_config(page_title="GORS HR5 Manual Dashboard", page_icon="🔄", layout="wide")

st.markdown("""
<style>
.stApp { background:#0b0f17; color:#f8fafc; }
.block-container { max-width:none; padding:2rem 2.5rem; }
.manual-hero { border:1px solid #334155; border-radius:18px; padding:24px; background:#111827; margin-bottom:18px; }
.manual-title { font-size:2.0rem; font-weight:950; color:#f8fafc; }
.manual-sub { color:#cbd5e1; margin-top:6px; }
.action-box { border:3px solid #fbbf24; border-radius:18px; padding:24px; background:#422006; margin:20px 0; }
.action-title { font-size:2.2rem; font-weight:950; color:#fef3c7; }
.action-line { font-size:1.15rem; color:#fffbeb; margin-top:8px; }
.safe-box { border:2px solid #22c55e; border-radius:18px; padding:24px; background:#052e16; margin:20px 0; }
.risk-on { color:#86efac; font-weight:950; }
.risk-off { color:#fbbf24; font-weight:950; }
</style>
""", unsafe_allow_html=True)


def top3(row):
    return [x for x in (row.get("top1"), row.get("top2"), row.get("top3")) if x]


def build_rotation_history(decisions):
    ordered = list(reversed(decisions))
    result = []
    previous = None
    for current in ordered:
        current_top = top3(current)
        if previous is None:
            signal, from_etf, to_etf, reason = "BASELINE", "—", "—", "First recorded GORS decision"
        else:
            previous_top = top3(previous)
            entered = [x for x in current_top if x not in previous_top]
            exited = [x for x in previous_top if x not in current_top]
            if current_top == previous_top:
                signal, from_etf, to_etf, reason = "NO ROTATION", "—", "—", "Top-3 composition/order unchanged"
            else:
                signal = "ROTATION"
                from_etf = ", ".join(exited) if exited else "—"
                to_etf = ", ".join(entered) if entered else "—"
                reason = current.get("note") or "GORS Top-3 changed"
        result.append({"Date": current.get("decision_date"), "Signal": signal, "From": from_etf,
                       "To": to_etf, "Top 3": " / ".join(current_top) if current_top else "—", "Reason": reason})
        previous = current
    return list(reversed(result))


def format_money(value):
    return f"₹{float(value):,.0f}"


st.markdown("<div class='manual-title'>🔄 Frozen HR5 Manual Trading Dashboard</div>", unsafe_allow_html=True)
st.caption("Signal-only dashboard. No broker orders are placed or routed by GORS.")

snapshot, kite_rows = latest_kite_snapshot()
decisions = get_decisions(limit=250)
previous_risk = str(decisions[0].get("risk_state", "RISK ON")).replace("-", " ") if decisions else "RISK ON"

try:
    market_data = load_market_data()
    signal = calculate_gors_signal(market_data, as_of=datetime.now(timezone.utc).date())
except Exception as exc:
    st.error(f"Cannot produce a safe GORS signal: {exc}")
    st.info("The dashboard intentionally refuses to use partial or incomplete market data.")
    st.stop()

holdings = build_holdings_table(kite_rows, signal["prices"])
holdings_value = float(holdings["Portfolio Value"].sum()) if not holdings.empty else 0.0
cash = float(snapshot["cash"]) if snapshot else 0.0
equity = holdings_value + cash
target_exposure_value = equity * float(signal["target_exposure_pct"])
actual_exposure_pct = holdings_value / equity if equity else 0.0
last_update = snapshot["snapshot_time"] if snapshot else "No Kite snapshot"
risk_class = "risk-on" if signal["risk_state"] == "RISK ON" else "risk-off"

st.markdown(
    f"""<div class='manual-hero'>
    <div class='manual-title {risk_class}'>{signal['risk_state']}</div>
    <div class='manual-sub'>Signal date: <b>{signal['signal_date']}</b> (latest completed common trading date)</div>
    <div class='manual-sub'>Frozen config: HoldRank {HOLD_RANK} • Drawdown {DD_TRIGGER:.0%} • Recovery {RECOVERY_FRACTION:.0%} of trigger • Risk-off {RISK_OFF_EXPOSURE:.0%} • Cost {PRODUCTION_COST:.2%} • RSI(14) {RSI_EXIT}/{RSI_FULL_EXIT}</div>
    </div>""", unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Target Exposure", f"{signal['target_exposure_pct']:.0%}", format_money(target_exposure_value))
c2.metric("Actual Exposure", f"{actual_exposure_pct:.0%}", format_money(holdings_value))
c3.metric("Portfolio Equity", format_money(equity))
c4.metric("Current Drawdown", f"{signal['current_drawdown']:.2%}")
c5.metric("Last Update", last_update)

st.subheader("Top 3")
top3_df = pd.DataFrame(signal["top3_table"])
top3_df["Signal/Score"] = top3_df["Signal/Score"].map(lambda x: f"{x:.2%}")
top3_df["Price"] = top3_df["Price"].map(lambda x: f"₹{x:,.2f}")
st.dataframe(top3_df[["Rank", "ETF", "Signal/Score", "Price", "Status"]], use_container_width=True, hide_index=True)

st.subheader("Current holdings")
if snapshot and not holdings.empty:
    show_holdings = holdings.copy()
    show_holdings["Price"] = show_holdings["Price"].map(lambda x: f"₹{x:,.2f}")
    show_holdings["Portfolio Value"] = show_holdings["Portfolio Value"].map(format_money)
    show_holdings["Weight"] = show_holdings["Weight"].map(lambda x: f"{x:.1%}")
    st.dataframe(show_holdings[["ETF", "Quantity", "Price", "Portfolio Value", "Weight"]], use_container_width=True, hide_index=True)
else:
    st.warning("No Kite holdings snapshot is available. Quantity/value-specific actions cannot be determined.")

st.markdown("### TODAY'S ACTION")
if signal["risk_state"] == "RISK OFF":
    st.markdown("<div class='action-box'><div class='action-title'>RISK-OFF</div><div class='action-line'>Target portfolio exposure is reduced to approximately 50%.</div></div>", unsafe_allow_html=True)
elif previous_risk == "RISK OFF" and signal["risk_state"] == "RISK ON":
    st.markdown("<div class='action-box'><div class='action-title'>RISK-ON</div><div class='action-line'>Normal 100% target exposure is restored.</div></div>", unsafe_allow_html=True)

actions = build_safe_manual_actions(signal, kite_rows, cash) if snapshot else []
if actions:
    action_rows = pd.DataFrame([a.__dict__ for a in actions]).rename(columns={"etf":"ETF", "action":"Action", "quantity":"Quantity", "approximate_value":"Approximate Value", "reason":"Reason", "signal_date":"Signal Date"})
    action_rows["Approximate Value"] = action_rows["Approximate Value"].map(lambda x: "—" if pd.isna(x) else format_money(x))
    st.dataframe(action_rows, use_container_width=True, hide_index=True)
else:
    st.markdown("<div class='safe-box'><div class='action-title'>HOLD</div><div class='action-line'>HOLD — No GORS action required.</div><div class='action-line'>Signal date: " + signal["signal_date"] + "</div></div>", unsafe_allow_html=True)

st.caption("Manual execution boundary: verify Kite prices, funds and quantities yourself. This page does not contain broker order execution code.")

with st.expander("Rotation history from saved decisions"):
    if decisions:
        st.dataframe(pd.DataFrame(build_rotation_history(decisions)), use_container_width=True, hide_index=True)
    else:
        st.info("No GORS decision history is available yet.")
