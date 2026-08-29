import importlib
from datetime import date

import pandas as pd
import streamlit as st

from gors_db import get_decisions

st.set_page_config(page_title="GORS Manual Trading Dashboard", page_icon="📊", layout="wide")

st.markdown(
    """
    <style>
    #MainMenu, footer {visibility:hidden;}
    .block-container {max-width:none;padding:1.25rem 2rem 2.5rem;}
    .hero {border:1px solid #334155;border-radius:18px;padding:22px 24px;background:#111827;margin-bottom:16px;}
    .title {font-size:2rem;font-weight:900;color:#f8fafc;}
    .muted {color:#94a3b8;}
    .action {border-radius:14px;padding:18px 20px;margin:8px 0;font-size:1.2rem;font-weight:900;border:1px solid #475569;background:#172033;}
    .risk-on {border-color:#16835b;background:#062e24;color:#d1fae5;}
    .risk-off {border-color:#b45309;background:#422006;color:#fef3c7;}
    .hold {border-color:#475569;background:#172033;color:#e2e8f0;}
    </style>
    """,
    unsafe_allow_html=True,
)

FROZEN = {
    "HoldRank": 5,
    "TopN": 3,
    "RSI": "14 / 85",
    "DD": "8%",
    "Recovery": "75%",
    "RiskOffExposure": "50%",
    "Cost": "0.25%",
}


def top3(row):
    return [str(row.get(k)).strip() for k in ("top1", "top2", "top3") if row.get(k)]


def safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def latest_decision():
    decisions = get_decisions(limit=250)
    return decisions[0] if decisions else None, decisions


def render_action(decision):
    risk = str(decision.get("risk_state") or decision.get("risk") or "UNKNOWN").upper()
    top = top3(decision)
    decision_date = decision.get("decision_date") or "—"
    note = decision.get("note") or "Frozen GORS decision"

    if risk in {"RISK-OFF", "RISK OFF"}:
        css, headline = "risk-off", "RISK OFF — MAINTAIN 50% EXPOSURE"
    elif risk in {"RISK-ON", "RISK ON"}:
        css, headline = "risk-on", "RISK ON — TARGET FULL EXPOSURE"
    else:
        css, headline = "hold", "HOLD — VERIFY SIGNAL DATA"

    st.markdown(
        f"<div class='action {css}'>{headline}<div class='muted' style='font-size:.9rem;margin-top:6px;'>Signal date: {decision_date} · {note}</div></div>",
        unsafe_allow_html=True,
    )
    return risk, top, decision_date


st.markdown(
    "<div class='hero'><div class='title'>📊 GORS Manual Trading Dashboard</div>"
    "<div class='muted'>Frozen HR5 signal cockpit · signal-only · no broker order execution</div></div>",
    unsafe_allow_html=True,
)

latest, decisions = latest_decision()
if latest is None:
    st.warning("No saved GORS decision is available yet.")
    st.info("Run the frozen GORS calculation first, then return to this page.")
    st.stop()

risk, top, signal_date = render_action(latest)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Signal Date", str(signal_date))
c2.metric("Risk State", risk)
c3.metric("Top-3", len(top))
c4.metric("Strategy", "HR5 FROZEN")

st.subheader("Today's Target")
if top:
    target_rows = [{"Rank": i + 1, "ETF": etf, "Status": "TARGET HOLD"} for i, etf in enumerate(top)]
    st.dataframe(pd.DataFrame(target_rows), use_container_width=True, hide_index=True)
else:
    st.warning("The saved decision contains no Top-3 symbols.")

st.subheader("Frozen Configuration")
st.dataframe(
    pd.DataFrame([{
        "HoldRank": FROZEN["HoldRank"],
        "Top-N": FROZEN["TopN"],
        "RSI": FROZEN["RSI"],
        "DD Trigger": FROZEN["DD"],
        "Recovery": FROZEN["Recovery"],
        "Risk-Off Exposure": FROZEN["RiskOffExposure"],
        "Cost": FROZEN["Cost"],
    }]),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Decision History")
history_rows = []
for d in decisions:
    top_d = top3(d)
    history_rows.append({
        "Date": d.get("decision_date"),
        "Risk": d.get("risk_state") or d.get("risk"),
        "Top 1": top_d[0] if len(top_d) > 0 else "—",
        "Top 2": top_d[1] if len(top_d) > 1 else "—",
        "Top 3": top_d[2] if len(top_d) > 2 else "—",
        "Note": d.get("note") or "",
    })

st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)

st.markdown(
    "<div class='muted' style='margin-top:18px;'>"
    "Manual boundary: this dashboard does not place, modify, cancel, or route broker orders. "
    "Use the displayed frozen signal as the decision aid and execute manually in Kite."
    "</div>",
    unsafe_allow_html=True,
)
