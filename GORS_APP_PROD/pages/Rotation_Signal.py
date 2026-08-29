import streamlit as st
import pandas as pd

from gors_engine import get_current_signal
from gors_db import get_decisions, latest_kite_snapshot, save_decision

st.set_page_config(page_title="GORS Manual Trading", page_icon="🔄", layout="wide")

st.markdown("""
<style>
.stApp { background:#0b0f17; color:#f8fafc; }
.block-container { max-width:1500px; padding:1.6rem 2rem 3rem; }
.hero { border:1px solid #334155; border-radius:18px; padding:24px; background:#151c29; margin-bottom:18px; }
.hero-title { font-size:2rem; font-weight:900; }
.hero-sub { color:#94a3b8; margin-top:4px; }
.action { border:2px solid #475569; border-radius:16px; padding:22px; background:#111827; margin:14px 0 20px; }
.action-title { font-size:1.05rem; color:#94a3b8; font-weight:800; letter-spacing:.04em; }
.action-main { font-size:1.8rem; font-weight:950; margin-top:8px; }
.muted { color:#94a3b8; }
.small { font-size:.88rem; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='hero'><div class='hero-title'>🔄 GORS Manual Trading Dashboard</div><div class='hero-sub'>Frozen HR5 signal • Top-3 • drawdown risk control • manual execution only</div></div>", unsafe_allow_html=True)

if st.button("🔄 Refresh signal", type="primary"):
    st.cache_data.clear()
    st.rerun()

@st.cache_data(ttl=900, show_spinner="Calculating frozen GORS signal from completed market data…")
def load_signal():
    return get_current_signal()

try:
    signal = load_signal()
except Exception as exc:
    st.error(f"GORS signal unavailable: {exc}")
    st.info("No action should be taken until the frozen engine completes successfully. This dashboard never places broker orders.")
    st.stop()

risk = signal["risk_state"]
target = signal["target_exposure"]
actual = signal["actual_exposure"]
dd = signal["drawdown"]
holdings = pd.DataFrame(signal["holdings"])
top3 = pd.DataFrame(signal["top3"])

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Signal Date", signal["signal_date"])
c2.metric("Risk State", risk)
c3.metric("Target Exposure", f"{target:.1%}")
c4.metric("Actual Exposure", f"{actual:.1%}")
c5.metric("Drawdown", f"{dd:.2%}")

st.markdown("<div class='action'><div class='action-title'>TODAY'S ACTION</div><div class='action-main'>Review target holdings below and manually execute only the required Kite changes.</div><div class='muted small'>GORS calculates the decision; it does not place, modify, or cancel broker orders.</div></div>", unsafe_allow_html=True)

st.subheader("Frozen HR5 Signal")
left, right = st.columns([1, 1])
with left:
    st.write("**Configuration**")
    st.write("HoldRank 5 • Top-3 • RSI(14) 85/100 • DD trigger 8% • Recovery 75% • Risk-off exposure 50% • Cost 0.25%")
    st.write(f"**Equity:** ₹{signal['equity']:,.2f}  |  **Cash:** ₹{signal['cash']:,.2f}")
with right:
    st.write("**Research metrics**")
    m = signal["metrics"]
    a, b, c = st.columns(3)
    a.metric("CAGR", f"{m['CAGR']:.2%}")
    b.metric("Max DD", f"{m['MaxDD']:.2%}")
    c.metric("Sharpe", f"{m['Sharpe']:.3f}")
    st.caption(f"Trades: {signal['trades']} • Annual turnover: {signal['annual_turnover']:.2f}x • Risk events: {signal['risk_events']}")

st.subheader("Top 3 — Frozen Engine")
if not top3.empty:
    top3["126D Return"] = top3["126D Return"].map(lambda x: f"{x:.2%}")
    top3["Status"] = top3["Held"].map(lambda x: "HOLD" if x else "TARGET")
    st.dataframe(top3[["ETF", "126D Return", "Status"]], use_container_width=True, hide_index=True)
else:
    st.warning("No eligible Top-3 returned by the frozen engine.")

st.subheader("Target Holdings")
if holdings.empty:
    st.info("Frozen engine currently has no invested holdings.")
else:
    holdings["Quantity"] = holdings["Quantity"].map(lambda x: round(float(x), 4))
    st.dataframe(holdings, use_container_width=True, hide_index=True)

snapshot, kite_rows = latest_kite_snapshot()
if snapshot:
    st.subheader("Kite Reconciliation")
    kite = pd.DataFrame(kite_rows)
    if not kite.empty:
        kite_qty = {str(r["etf"]): float(r["quantity"]) for r in kite_rows}
        target_qty = {str(r["ETF"]): float(r["Quantity"]) for r in signal["holdings"]}
        names = sorted(set(kite_qty) | set(target_qty))
        recon = []
        for name in names:
            kq = kite_qty.get(name, 0.0)
            tq = target_qty.get(name, 0.0)
            delta = tq - kq
            recon.append({"ETF": name, "Kite Qty": kq, "Target Qty": tq, "Delta": delta, "Action": "BUY" if delta > 1e-9 else "SELL" if delta < -1e-9 else "HOLD"})
        recon_df = pd.DataFrame(recon)
        st.caption(f"Latest Kite snapshot: {snapshot['snapshot_time']} • source: {snapshot['source']}")
        st.dataframe(recon_df, use_container_width=True, hide_index=True)
        changes = recon_df[recon_df["Action"] != "HOLD"]
        if changes.empty:
            st.success("Kite holdings match the frozen engine target. TODAY'S ACTION: HOLD.")
        else:
            st.warning("Manual changes are indicated above. Verify quantities and prices in Kite before placing any order.")
    else:
        st.info("Latest Kite snapshot has no holdings rows.")
else:
    st.info("No Kite snapshot has been imported yet. Target holdings above remain the source of truth for the manual decision.")

st.subheader("Recent Engine Events")
events = pd.DataFrame(signal["events"])
if not events.empty:
    st.dataframe(events, use_container_width=True, hide_index=True)
else:
    st.caption("No recent engine events.")

st.subheader("Recorded Decision History")
decisions = get_decisions(limit=100)
if decisions:
    st.dataframe(pd.DataFrame(decisions), use_container_width=True, hide_index=True)
else:
    st.caption("No decisions recorded yet.")

with st.expander("Save today's calculated decision"):
    note = st.text_input("Optional note", value="Frozen HR5 engine signal")
    if st.button("Save decision"):
        save_decision(signal["signal_date"], "RISK_OFF" if risk == "RISK OFF" else "RISK_ON", risk, [x["ETF"] for x in signal["top3"]], note)
        st.success("Decision saved.")

st.caption("Manual-only boundary: this page reads market data and stored Kite snapshots, calculates the frozen GORS decision, and never sends broker orders.")
