from datetime import date

import pandas as pd
import streamlit as st

from gors_db import get_decisions
from rotation_history import rotation_history, top3

st.set_page_config(page_title="GORS History", page_icon="🕘", layout="wide")

st.title("🕘 ETF Rotation History")
st.caption("Shows when GORS Top 3 ETF membership changed. Re-ordering the same three ETFs is not a rotation.")

decisions = get_decisions(limit=1000)
changes = rotation_history(decisions)

if decisions:
    latest = max(decisions, key=lambda r: str(r.get("decision_date") or ""))
    current = top3(latest)
    last_change = changes[0]["Date"] if changes else "No rotation recorded"
    try:
        days_since = (date.today() - date.fromisoformat(last_change)).days if changes else "—"
    except (TypeError, ValueError):
        days_since = "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Top 3", " · ".join(current) or "—")
    c2.metric("Last ETF Change", last_change)
    c3.metric("Days Since Change", days_since)
    c4.metric("Total Rotations", len(changes))

    if changes:
        st.subheader("ETF Membership Changes")
        st.dataframe(pd.DataFrame(changes), width="stretch", hide_index=True)
    else:
        st.info("No ETF membership changes are recorded in GORS decision history yet.")

    st.subheader("Daily Decision Audit")
    audit = pd.DataFrame(decisions)
    audit_cols = [c for c in ["decision_date", "decision", "risk_state", "top1", "top2", "top3", "created_at"] if c in audit.columns]
    st.dataframe(audit[audit_cols], width="stretch", hide_index=True)
else:
    st.info("No GORS decisions are recorded yet.")
