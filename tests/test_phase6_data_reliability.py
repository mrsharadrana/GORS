import pandas as pd
import pytest

from GORS_APP_PROD.market_data_reliability import validate_market_data, write_cache, read_cache


def valid_frame():
    idx = pd.bdate_range("2026-01-01", periods=3)
    return pd.DataFrame({"NIFTY": [100, 101, 102], "GOLD": [50, 51, 52]}, index=idx)


def test_valid_market_data_passes():
    ok, reason = validate_market_data(valid_frame(), ["NIFTY", "GOLD"])
    assert ok and reason == "ok"


def test_missing_ticker_rejected():
    ok, reason = validate_market_data(valid_frame(), ["NIFTY", "SILVER"])
    assert not ok
    assert "SILVER" in reason


def test_missing_price_rejected():
    frame = valid_frame()
    frame.loc[frame.index[1], "GOLD"] = float("nan")
    ok, _ = validate_market_data(frame, ["NIFTY", "GOLD"])
    assert not ok


def test_non_positive_price_rejected():
    frame = valid_frame()
    frame.loc[frame.index[1], "NIFTY"] = 0
    ok, _ = validate_market_data(frame, ["NIFTY", "GOLD"])
    assert not ok


def test_cache_round_trip(tmp_path, monkeypatch):
    import GORS_APP_PROD.market_data_reliability as reliability
    monkeypatch.setattr(reliability, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(reliability, "CACHE_FILE", tmp_path / "market_data.csv")
    monkeypatch.setattr(reliability, "META_FILE", tmp_path / "market_data_meta.json")
    frame = valid_frame()
    write_cache(frame, ["NIFTY", "GOLD"])
    restored, refreshed = read_cache(["NIFTY", "GOLD"])
    pd.testing.assert_frame_equal(restored, frame)
    assert refreshed is not None
