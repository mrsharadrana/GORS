from GORS_APP_PROD.rotation_history import rotation_history


def test_order_only_change_is_ignored():
    decisions = [
        {"decision_date": "2026-08-29", "top1": "MON100", "top2": "SMALLCAP", "top3": "GOLDBEES"},
        {"decision_date": "2026-08-30", "top1": "GOLDBEES", "top2": "MON100", "top3": "SMALLCAP"},
    ]
    assert rotation_history(decisions) == []


def test_membership_change_is_recorded():
    decisions = [
        {"decision_date": "2026-08-29", "top1": "MON100", "top2": "BANKBEES", "top3": "GOLDBEES", "risk_state": "RISK-ON"},
        {"decision_date": "2026-08-30", "top1": "MON100", "top2": "SMALLCAP", "top3": "GOLDBEES", "risk_state": "RISK-ON"},
    ]
    result = rotation_history(decisions)
    assert len(result) == 1
    assert result[0]["Added"] == "SMALLCAP"
    assert result[0]["Removed"] == "BANKBEES"
