from __future__ import annotations

from datetime import datetime, timezone

from gors_engine import TICKERS, apply_mon100_correction, build_panel, download_market_data, mon100_audit
from market_data_reliability import write_cache


if __name__ == "__main__":
    raw = download_market_data()
    corrected = apply_mon100_correction(raw)
    if not mon100_audit(raw, corrected):
        raise RuntimeError("REFRESH REJECTED: MON100 correction gate failed")
    panel = build_panel(corrected)
    write_cache(panel, list(TICKERS), datetime.now(timezone.utc))
    print(f"Validated Yahoo refresh complete: {len(panel)} rows, {len(TICKERS)} tickers")
