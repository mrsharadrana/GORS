def top3(row):
    return [str(row.get(k)).strip() for k in ("top1", "top2", "top3") if row.get(k)]


def rotation_history(decisions):
    """Return only dates where Top-3 ETF membership changed.

    Re-ordering the same three ETFs is deliberately ignored.
    """
    ordered = sorted(
        decisions,
        key=lambda r: (str(r.get("decision_date") or ""), str(r.get("created_at") or "")),
    )
    changes = []
    previous = None
    for row in ordered:
        current = top3(row)
        current_set = frozenset(current)
        if previous is None:
            previous = current_set
            continue
        if current_set != previous:
            changes.append(
                {
                    "Date": row.get("decision_date"),
                    "Previous Top 3": " · ".join(sorted(previous)),
                    "New Top 3": " · ".join(current),
                    "Added": " · ".join(sorted(current_set - previous)),
                    "Removed": " · ".join(sorted(previous - current_set)),
                    "Risk State": row.get("risk_state"),
                }
            )
            previous = current_set
    return list(reversed(changes))
