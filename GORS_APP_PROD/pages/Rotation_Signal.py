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

st.markdown("<div class='gors-card'><div class='gors-title'>🔄 GORS HR5 Dashboard</div><div class='muted'>Frozen strategy • Signal-only • No broker orders</div></div>",unsafe_allow_html=True)

snapshot,kite_rows=latest_kite_snapshot()
decisions=get_decisions(limit=250)
try:
    market_data=load_market_data()
    signal=calculate_gors_signal(market_data,as_of=datetime.now(timezone.utc).date())
except Exception as exc:
    st.error(f"Cannot produce a safe GORS signal: {exc}")
    st.stop()

holdings=build_holdings_table(kite_rows,signal["prices"])
holdings_value=float(holdings["Portfolio Value"].sum()) if not holdings.empty else 0.0
cash=float(snapshot["cash"]) if snapshot else 0.0
equity=holdings_value+cash
actual=holdings_value/equity if equity else 0.0
last_update=snapshot["snapshot_time"] if snapshot else "No snapshot"

st.info(f"Last Data Updated: {last_update}")
st.markdown(f"### {signal['risk_state']}")
st.caption(f"Signal date: {signal['signal_date']} • HoldRank {HOLD_RANK} • DD {DD_TRIGGER:.0%} • Risk-off {RISK_OFF_EXPOSURE:.0%} • Recovery {RECOVERY_FRACTION:.0%} • RSI {RSI_EXIT}/{RSI_FULL_EXIT}")

c1,c2=st.columns(2)
c1.metric("Target Exposure",f"{signal['target_exposure_pct']:.0%}",money(equity*float(signal['target_exposure_pct'])))
c2.metric("Actual Exposure",f"{actual:.0%}",money(holdings_value))
c1,c2=st.columns(2)
c1.metric("Portfolio Equity",money(equity))
c2.metric("Current Drawdown",f"{signal['current_drawdown']:.2%}")

st.subheader("Top 3")
ranks=strategy_top3(signal)[:3]
st.dataframe(pd.DataFrame([{"Rank":i,"ETF":e,"Price":f"₹{float(signal['prices'].get(e,0)):,.2f}"} for i,e in enumerate(ranks,1)]),use_container_width=True,hide_index=True)

st.subheader("Today's Action")
actions=build_safe_manual_actions(signal,kite_rows,cash) if snapshot else []
if actions:
    df=pd.DataFrame([a.__dict__ for a in actions]).rename(columns={"etf":"ETF","action":"Action","quantity":"Quantity","approximate_value":"Value","reason":"Reason","signal_date":"Signal Date"})
    df["Value"]=df["Value"].map(lambda x:"—" if pd.isna(x) else money(x))
    st.dataframe(df,use_container_width=True,hide_index=True)
else:
    st.success(f"HOLD — No GORS action required. Signal date: {signal['signal_date']}")

with st.expander("Current Holdings"):
    if snapshot and not holdings.empty:
        h=holdings.copy(); h["Price"]=h["Price"].map(lambda x:f"₹{x:,.2f}"); h["Portfolio Value"]=h["Portfolio Value"].map(money); h["Weight"]=h["Weight"].map(lambda x:f"{x:.1%}")
        st.dataframe(h[["ETF","Quantity","Price","Portfolio Value","Weight"]],use_container_width=True,hide_index=True)
    else: st.warning("No Kite holdings snapshot available.")

with st.expander("Rotation History"):
    if decisions:
        rows=[]
        ordered=list(reversed(decisions))
        prev=None
        for d in ordered:
            cur=top3(d); old=top3(prev) if prev else []
            rows.append({"Date":d.get("decision_date"),"Signal":"BASELINE" if prev is None else ("NO ROTATION" if cur==old else "ROTATION"),"Top 3":" / ".join(cur)})
            prev=d
        st.dataframe(pd.DataFrame(list(reversed(rows))),use_container_width=True,hide_index=True)
    else: st.info("No decision history available.")

st.caption("Manual execution boundary: verify Kite prices, funds and quantities yourself.")
