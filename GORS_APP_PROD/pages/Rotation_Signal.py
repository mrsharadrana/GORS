import streamlit as st
import pandas as pd

from gors_db import get_decisions

st.set_page_config(page_title="GORS Rotation Signal", page_icon="🔄", layout="wide")

st.markdown("""
<style>
.stApp { background:#0b0f17; color:#f8fafc; }
.block-container { max-width:none; padding:2rem 2.5rem; }
.rotation-card { border:1px solid #334155; border-radius:16px; padding:22px; background:#151c29; margin-bottom:18px; }
.rotation-title { font-size:1.8rem; font-weight:900; color:#f8fafc; }
.rotation-date { color:#94a3b8; font-size:.95rem; margin-top:5px; }
.rotation-main { font-size:1.5rem; font-weight:900; margin-top:14px; }
.rotation-sub { color:#cbd5e1; margin-top:6px; }
</style>
""", unsafe_allow_html=True)


def top3(row):
    return [x for x in (row.get("top1"), row.get("top2"), row.get("top3")) if x]


def build_rotation_history(decisions):
    # decision_history is returned newest first. Compare each decision with
    # the immediately preceding recorded GORS decision.
    ordered = list(reversed(decisions))
    result = []

    previous = None
    for current in ordered:
        current_top = top3(current)
        if previous is None:
            signal = "BASELINE"
            from_etf = "—"
            to_etf = "—"
            reason = "First recorded GORS decision"
        else:
            previous_top = top3(previous)
            entered = [x for x in current_top if x not in previous_top]
            exited = [x for x in previous_top if x not in current_top]
            changed = current_top != previous_top

            if not changed:
                signal = "NO ROTATION"
                from_etf = "—"
                to_etf = "—"
                reason = "Top-3 composition/order unchanged"
            else:
                signal = "ROTATION"
                from_etf = ", ".join(exited) if exited else "—"
                to_etf = ", ".join(entered) if entered else "—"
                reason = current.get("note") or "GORS Top-3 changed"

        result.append({
            "Date": current.get("decision_date"),
            "Signal": signal,
            "From": from_etf,
            "To": to_etf,
            "Top 3": " / ".join(current_top) if current_top else "—",
            "Reason": reason,
        })
        previous = current

    return list(reversed(result))


st.markdown("<div class='rotation-title'>🔄 Rotation Signal</div>", unsafe_allow_html=True)
st.caption("Dated rotation history derived from the existing GORS decision history. Strategy rules are not modified.")

decisions = get_decisions(limit=250)

if not decisions:
    st.info("No GORS decision history is available yet.")
    st.stop()

history = build_rotation_history(decisions)
rotations = [r for r in history if r["Signal"] == "ROTATION"]
latest = history[0]

if latest["Signal"] == "ROTATION":
    st.markdown(
        f"""<div class='rotation-card'>
        <div class='rotation-date'>{latest['Date']}</div>
        <div class='rotation-main'>🔄 ROTATION: {latest['From']} → {latest['To']}</div>
        <div class='rotation-sub'>Top 3: {latest['Top 3']}</div>
        <div class='rotation-sub'>Reason: {latest['Reason']}</div>
        </div>""",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f"""<div class='rotation-card'>
        <div class='rotation-date'>{latest['Date']}</div>
        <div class='rotation-main'>✓ NO ROTATION</div>
        <div class='rotation-sub'>Top 3: {latest['Top 3']}</div>
        </div>""",
        unsafe_allow_html=True,
    )

st.subheader("Rotation History")

if rotations:
    st.dataframe(pd.DataFrame(rotations), use_container_width=True, hide_index=True)
else:
    st.info("No rotation has been detected in the recorded decision history.")

with st.expander("All GORS decision dates"):
    st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
