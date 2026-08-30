from datetime import datetime

import market_refresh


def test_refresh_uses_india_timezone():
    assert market_refresh.IST.key == "Asia/Kolkata"


def test_refresh_persists_latest_signal(monkeypatch):
    calls = {}

    monkeypatch.setattr(market_refresh, "init_db", lambda: calls.setdefault("init", True))
    monkeypatch.setattr(market_refresh, "load_market_data", lambda: "panel")
    monkeypatch.setattr(
        market_refresh,
        "calculate_gors_signal",
        lambda panel, as_of: {
            "signal_date": "2026-08-28",
            "top3": ["MON100", "GOLD", "NIFTY"],
            "risk_state": "RISK ON",
        },
    )
    monkeypatch.setattr(
        market_refresh,
        "save_decision",
        lambda signal_date, decision, risk_state, top3, note: calls.update(
            signal_date=signal_date,
            decision=decision,
            risk_state=risk_state,
            top3=top3,
            note=note,
        ),
    )
    monkeypatch.setattr(market_refresh, "record_integrity", lambda *args: None)

    market_refresh.main()

    assert calls["init"] is True
    assert calls["signal_date"] == "2026-08-28"
    assert calls["decision"] == "BUY / HOLD"
    assert calls["risk_state"] == "RISK ON"
    assert calls["top3"] == ["MON100", "GOLD", "NIFTY"]
    assert "Asia/Kolkata" in calls["note"]
