from datetime import date

import pandas as pd
import streamlit as st

from gors_db import get_decisions

st.set_page_config(page_title="GORS History", page_icon="🕘", layout="wide")

st.markdown(
    """
    <style>
    .hero {border:1px solid #334155;border-radius:18px;padding:24px 28px;background:#111827;margin-bottom:18px;}
    .eyebrow {font-size:.82rem;font-weight:850;letter-spacing:.08em;color:#94a3b8;text-transform:uppercase;}
    .title {font-size:2.15rem;font-weight:900;color:#f8fafc;}
    .sub {color:#cbd5e1;font-size:1.03rem;margin-top:6px;}
    .stat {border:1px solid #334155;border-radius:14px;padding:18px;background:#151c29;}
    .label {font-size:.86rem;color:#94a3b8;font-weight:800;text-transform:uppercase;}
    .value {font-size:1.7rem;color:#f8fafc;font-weight:900;margin-top:5px;}
    </style>
    """,
    unsafe_allow_html=True,
)


def top3(row):
    return [str(row.get(k)).strip() for k in ("top1", "top2", "top3") if row.get(k)]


def rotation_history(decisions):
    """Return only dates where Top-3 ETF membership changed.

    Ranking/order changes alone are deliberately ignored. The first recorded
    decision establishes the baseline and is not labelled as a rotation.
    """
    ordered = sorted(decisions, key=lambda r: (str(r.get("decision_date") or ""), int(r.get("id") or 0)))
    changes = []
    previous = None

    for row in ordered:
        current = top3(row)
        current_set = frozenset(current)
        if previous is None:
            previous = current_set
            continue
        if current_set != previous:
            changes.append({
                "Date": row.get("decision_date"),
                "Previous Top 3": " · ".join(sorted(previous)),
                "New Top 3": " · ".join(current),
                "Risk State": row.get("risk_state"),
            })
            previous = current_set

    return list(reversed(changes))


st.markdown(
    """
    <div class='hero'>
      <div class='eyebrow'>GORS_APP_PROD • ROTATION AUDIT</div>
      <div class='title'>🕘 ETF Rotation History</div>
      <div class='sub'>Shows when the GORS Top 3 ETF membership changed. Re-ordering the same three ETFs is not treated as a rotation.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

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

    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='stat'><div class='label'>Current Top 3</div><div class='value'>{' · '.join(current) or '—'}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='stat'><div class='label'>Last ETF Change</div><div class='value'>{last_change}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='stat'><div class='label'>Total Rotations</div><div class='value'>{len(changes)}</div></div>", unsafe_allow_html=True)

    st.markdown("### Rotation Events")
    if changes:
        st.dataframe(pd.DataFrame(changes), width="stretch", hide_index=True)
    else:
        st.info("No ETF membership changes are recorded in GORS decision history yet.")

    st.markdown("### Daily Decision Audit")
    audit = pd.DataFrame(decisions)
    audit_cols = [c for c in ["decision_date", "decision", "risk_state", "top1", "top2", "top3", "created_at"] if c in audit.columns]
    st.dataframe(audit[audit_cols], width="stretch", hide_index=True)
else:
    st.info("No GORS decisions are recorded yet.")
