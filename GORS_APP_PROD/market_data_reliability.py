from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent / "data"
CACHE_FILE = CACHE_DIR / "market_data.csv"
META_FILE = CACHE_DIR / "market_data_meta.json"


def validate_market_data(data: pd.DataFrame, required_columns: list[str]) -> tuple[bool, str]:
    if data.empty:
        return False, "market data is empty"
    missing = [c for c in required_columns if c not in data.columns]
    if missing:
        return False, f"missing tickers: {', '.join(missing)}"
    if not isinstance(data.index, pd.DatetimeIndex):
        return False, "market-data index must be DatetimeIndex"
    if data.index.has_duplicates:
        return False, "market-data index contains duplicates"
    if not data.index.is_monotonic_increasing:
        return False, "market-data index is not sorted"
    if data[required_columns].isna().any().any():
        return False, "market data contains missing required prices"
    if (data[required_columns] <= 0).any().any():
        return False, "market data contains non-positive prices"
    return True, "ok"


def write_cache(data: pd.DataFrame, required_columns: list[str], refreshed_at: datetime | None = None) -> None:
    ok, reason = validate_market_data(data, required_columns)
    if not ok:
        raise RuntimeError(f"REFRESH REJECTED: {reason}")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".tmp")
    data[required_columns].to_csv(tmp, index_label="Date")
    tmp.replace(CACHE_FILE)
    stamp = refreshed_at or datetime.now(timezone.utc)
    META_FILE.write_text(json.dumps({"refreshed_at": stamp.isoformat(), "rows": len(data), "columns": required_columns}, indent=2), encoding="utf-8")


def read_cache(required_columns: list[str]) -> tuple[pd.DataFrame, datetime]:
    if not CACHE_FILE.exists() or not META_FILE.exists():
        raise FileNotFoundError("No validated market-data cache exists")
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    refreshed_at = datetime.fromisoformat(meta["refreshed_at"])
    data = pd.read_csv(CACHE_FILE, index_col="Date", parse_dates=True)
    ok, reason = validate_market_data(data, required_columns)
    if not ok:
        raise RuntimeError(f"CACHE REJECTED: {reason}")
    return data, refreshed_at
