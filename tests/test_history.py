from GORS_APP_PROD.pages.History import rotation_history


def test_rotation_history_ignores_order_only_changes():
    decisions = [
        {"decision_date": "2026-08-01", "id": 1, "top1": "MON100", "top2": "SMALLCAP", "top3": "GOLDBEES", "risk_state": "RISK-ON"},
        {"decision_date": "2026-08-02", "id": 2, "top1": "GOLDBEES", "top2": "MON100", "top3": "SMALLCAP", "risk_state": "RISK-ON"},
        {"decision_date": "2026-08-03", "id": 3, "top1": "MON100", "top2": "BANKBEES", "top3": "GOLDBEES", "risk_state": "RISK-ON"},
    ]
    changes = rotation_history(decisions)
    assert len(changes) == 1
    assert changes[0]["Date"] == "2026-08-03"
    assert "SMALLCAP" in changes[0]["Previous Top 3"]
    assert "BANKBEES" in changes[0]["New Top 3"]
