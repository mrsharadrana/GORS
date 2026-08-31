import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "GORS_APP_PROD"))
import cutoff_safe_backtest as safe
import gors_engine

def make_panel(days=260):
    idx = pd.bdate_range("2020-01-01", periods=days)
    return pd.DataFrame({name: 100.0 + np.arange(days) * (0.20 + i * 0.03) for i, name in enumerate(gors_engine.TICKERS)}, index=idx)

def test_post_cutoff_data_cannot_change_historical_backtest():
    base = make_panel(); cutoff = base.index[200]; shocked = base.copy(); shocked.loc[cutoff + pd.offsets.BDay(1):] *= 0.01
    a = safe.run(base, as_of=cutoff + pd.Timedelta(days=1)); b = safe.run(shocked, as_of=cutoff + pd.Timedelta(days=1))
    assert a["cutoff"] == cutoff and b["cutoff"] == cutoff
    pd.testing.assert_frame_equal(a["state"], b["state"]); pd.testing.assert_frame_equal(a["events"], b["events"]); assert a["metrics"] == b["metrics"]

def test_cutoff_uses_india_calendar_for_aware_timestamp():
    panel = make_panel(); cutoff = panel.index[200]
    as_of = (cutoff + pd.Timedelta(days=1) + pd.Timedelta(hours=5, minutes=30)).tz_localize("Asia/Kolkata")
    assert safe.latest_completed_date(panel, as_of) == cutoff

def test_data_before_cutoff_can_change_result():
    base = make_panel(); cutoff = base.index[200]; changed = base.copy(); changed.loc[cutoff, "NIFTY"] *= 0.80
    a = safe.run(base, as_of=cutoff + pd.Timedelta(days=1)); b = safe.run(changed, as_of=cutoff + pd.Timedelta(days=1))
    assert b["state"].iloc[-1]["Drawdown"] < a["state"].iloc[-1]["Drawdown"]
