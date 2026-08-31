from __future__ import annotations

from zoneinfo import ZoneInfo
import pandas as pd
import gors_engine

IST = ZoneInfo("Asia/Kolkata")

def normalize_as_of(as_of=None) -> pd.Timestamp:
    ts = pd.Timestamp.now(tz=IST) if as_of is None else pd.Timestamp(as_of)
    if ts.tzinfo is None:
        ts = ts.tz_localize(IST)
    else:
        ts = ts.tz_convert(IST)
    return ts.tz_localize(None).normalize()

def latest_completed_date(panel: pd.DataFrame, as_of=None) -> pd.Timestamp:
    if panel.empty:
        raise RuntimeError("No market data available.")
    idx = pd.DatetimeIndex(panel.index)
    if idx.tz is not None:
        idx = idx.tz_convert(IST).tz_localize(None)
    cutoff = normalize_as_of(as_of)
    completed = idx[idx < cutoff]
    if len(completed) == 0:
        raise RuntimeError("No completed market-data date exists before as_of.")
    return completed[-1]

def slice_to_cutoff(panel: pd.DataFrame, as_of=None):
    cutoff = latest_completed_date(panel, as_of)
    data = panel.copy()
    idx = pd.DatetimeIndex(data.index)
    if idx.tz is not None:
        idx = idx.tz_convert(IST).tz_localize(None)
        data.index = idx
    data = data[~data.index.duplicated(keep="last")].sort_index()
    return data.loc[:cutoff].copy(), cutoff

def run(panel: pd.DataFrame, as_of=None):
    scoped, cutoff = slice_to_cutoff(panel, as_of)
    start = gors_engine.first_valid(scoped)
    result = gors_engine.run_forensic(scoped, start)
    result["cutoff"] = cutoff
    return result
