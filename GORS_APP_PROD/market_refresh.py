"""Scheduled production market-data refresh for GORS.

This job deliberately calls the frozen GORS engine; it does not change strategy
parameters or broker execution behavior. It refreshes Yahoo Finance data,
calculates the latest signal, and persists the decision timestamp to the
configured production database.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from gors_db import init_db, record_integrity, save_decision
from gors_engine import calculate_gors_signal, load_market_data

IST = ZoneInfo("Asia/Kolkata")


def main() -> None:
    init_db()
    started_at = datetime.now(IST)
    panel = load_market_data()
    signal = calculate_gors_signal(panel, as_of=started_at)
    top3 = signal.get("top3", [])[:3]
    risk_state = signal.get("risk_state", "UNKNOWN")
    signal_date = signal["signal_date"]

    # Stamp the completed refresh only after Yahoo data and GORS calculation finish.
    completed_at = datetime.now(IST)
    updated_at = completed_at.isoformat(timespec="seconds")
    note = (
        f"Automated Yahoo Finance refresh completed at {updated_at} ({IST.key}); "
        f"signal date={signal_date}; Top-3={','.join(top3)}; "
        f"risk={risk_state}."
    )
    save_decision(signal_date, "BUY / HOLD", risk_state, top3, note)
    record_integrity("INFO", "market_refresh", note)
    print(f"GORS refresh complete: {updated_at} | signal={signal_date} | top3={top3} | risk={risk_state}")


if __name__ == "__main__":
    main()
