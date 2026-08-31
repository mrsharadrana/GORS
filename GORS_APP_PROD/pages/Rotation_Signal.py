from __future__ import annotations

import pandas as pd
import streamlit as st

from gors_db import get_decisions, get_integrity_events, latest_kite_snapshot
from gors_dashboard_helpers import build_safe_manual_actions
from gors_decision import get_current_gors_decision
from gors_engine import (
    DD_TRIGGER, HOLD_RANK, RECOVERY_FRACTION, RISK_OFF_EXPOSURE,
    RSI_FULL_EXIT, RSI_EXIT, build_holdings_table,
)

st.set_page_config(page_title="GORS HR5", page_icon="🔄", layout="wide")

st.markdown("""
<style>
.block-container{max-width:1100px;padding:1rem 1rem 3rem}
@media(max-width:700px){.block-container{padding:.65rem .55rem 2rem}.stMetric{padding:.35rem}.stDataFrame{font-size:.85rem}}
.gors-card{border:1px solid #334155;border-radius:16px;padding:18px;margin:10px 0;background:#111827}
.gors-title{font-size:1.8rem;font-weight:900}.muted{color:#94a3b8}
</style>
""", unsafe_allow_html=True)

def money(v): return f"₹{float(v):,.0f}"

def top3(row): return [x for x in (row.get("top1"),row.get("top2"),row.get("top3")) if x]

def rank_delta(signal, etf):
    current = next((r.get("Rank") for r in signal.get("top3_table", []) if r.get("ETF") == etf), None)
    dates = sorted({x.get("Date") for x in signal.get("selection_history", []) if x.get("Date")})
    if len(dates) < 2: return current, None
    prior_date = dates[-2]
    prior = next((x.get("Rank") for x in signal.get("selection_history", []) if x.get("Date") == prior_date and x.get("ETF") == etf), None)
    return current, (prior - current) if current is not None and prior is not None else None

st.markdown("<div class='gors-card'><div class='gors-title'>🔄 GORS HR5 Decision Dashboard</div><div class='muted'>Frozen strategy • Decision support only • No broker orders</div></div>",unsafe_allow_html=True)

snapshot, kite_rows = latest_kite_snapshot()
decisions = get_decisions(limit=250)
integrity = get_integrity_events(limit=10)
try:
    decision = get_current_gors_decision()
    signal = decision["signal"]
except Exception as exc:
    st.error(f"Cannot produce a safe GORS signal: {exc}")
    st.stop()

holdings = build_holdings_table(kite_rows, signal["prices"])
holdings_value = float(holdings["Portfolio Value"].sum()) if not holdings.empty else 0.0
cash = float(snapshot["cash"]) if snapshot else float(signal.get("cash", 0.0))
equity = holdings_value + cash
actual = holdings_value / equity if equity else 0.0
last_update = snapshot["snapshot_time"] if snapshot else "No portfolio snapshot"

st.info(f"Last Data Updated: {last_update}")
st.markdown(f"### {decision['risk_state']}")
st.caption(f"Signal date: {decision['signal_date']} • Ranking date: {decision['ranking_date']} • HoldRank {HOLD_RANK} • DD {DD_TRIGGER:.0%} • Risk-off {RISK_OFF_EXPOSURE:.0%} • Recovery {RECOVERY_FRACTION:.0%} • RSI {RSI_EXIT}/{RSI_FULL_EXIT}")

c1,c2,c3,c4 = st.columns(4)
c1.metric("Target Exposure", f"{decision['target_exposure_pct']:.0%}", money(equity * decision['target_exposure_pct']))
c2.metric("Actual Exposure", f"{actual:.0%}", money(holdings_value))
c3.metric("Portfolio Equity", money(equity))
c4.metric("Current Drawdown", f"{decision['current_drawdown']:.2%}")

st.subheader("Today's Decision")
actions = build_safe_manual_actions(signal, kite_rows, cash) if snapshot else []
if actions:
    df = pd.DataFrame([a.__dict__ for a in actions]).rename(columns={"etf":"ETF","action":"Action","quantity":"Quantity","approximate_value":"Value","reason":"Reason","signal_date":"Signal Date"})
    df["Value"] = df["Value"].map(lambda x: "—" if pd.isna(x) else money(x))
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.success(f"HOLD — No GORS action required. Signal date: {decision['signal_date']}")

st.subheader("Top 3 Ranking")
rank_rows=[]
for row in signal.get("top3_table", [])[:3]:
    rank, delta = rank_delta(signal, row["ETF"])
    rank_rows.append({"Rank":rank,"Change":("↑"+str(delta) if delta and delta>0 else ("↓"+str(abs(delta)) if delta and delta<0 else "—")),"ETF":row["ETF"],"Score":row.get("Signal/Score"),"RSI":row.get("RSI"),"Price":row.get("Price"),"Status":row.get("Status")})
st.dataframe(pd.DataFrame(rank_rows), use_container_width=True, hide_index=True)

st.subheader("Portfolio Drift")
drift_target=float(decision["target_exposure_pct"])
drift=actual-drift_target
if abs(drift) < 0.02:
    st.success(f"ON TARGET — exposure drift {drift:+.1%}")
elif drift > 0:
    st.warning(f"OVERWEIGHT — exposure drift {drift:+.1%}; target is {drift_target:.0%}")
else:
    st.warning(f"UNDERWEIGHT — exposure drift {drift:+.1%}; target is {drift_target:.0%}")

with st.expander("Risk Control"):
    r1,r2,r3 = st.columns(3)
    r1.metric("Risk State", decision["risk_state"])
    r2.metric("Drawdown", f"{decision['current_drawdown']:.2%}")
    r3.metric("Target Exposure", f"{decision['target_exposure_pct']:.0%}")
    if not signal.get("events", pd.DataFrame()).empty:
        st.dataframe(signal["events"].tail(20), use_container_width=True, hide_index=True)
    else:
        st.caption("No risk-state transition recorded in the current backtest window.")

with st.expander("Data Health"):
    st.write(f"**Signal date:** {decision['signal_date']}")
    st.write(f"**Ranking date:** {decision['ranking_date']}")
    st.write(f"**Portfolio snapshot:** {last_update}")
    st.write(f"**Universe prices:** {len(signal.get('prices', {}))}")
    if integrity:
        st.dataframe(pd.DataFrame(integrity), use_container_width=True, hide_index=True)
    else:
        st.success("No recent integrity events recorded.")

with st.expander("Current Holdings"):
    if snapshot and not holdings.empty:
        h=holdings.copy(); h["Price"]=h["Price"].map(lambda x:f"₹{x:,.2f}"); h["Portfolio Value"]=h["Portfolio Value"].map(money); h["Weight"]=h["Weight"].map(lambda x:f"{x:.1%}")
        st.dataframe(h[["ETF","Quantity","Price","Portfolio Value","Weight"]],use_container_width=True,hide_index=True)
    else:
        st.warning("No Kite holdings snapshot available.")

with st.expander("Rotation History"):
    if decisions:
        rows=[]; ordered=list(reversed(decisions)); prev=None
        for d in ordered:
            cur=top3(d); old=top3(prev) if prev else []
            rows.append({"Date":d.get("decision_date"),"Signal":"BASELINE" if prev is None else ("NO ROTATION" if cur==old else "ROTATION"),"Top 3":" / ".join(cur)})
            prev=d
        st.dataframe(pd.DataFrame(list(reversed(rows))),use_container_width=True,hide_index=True)
    else:
        st.info("No decision history available.")

st.caption("Manual execution boundary: verify Kite prices, funds and quantities yourself.")