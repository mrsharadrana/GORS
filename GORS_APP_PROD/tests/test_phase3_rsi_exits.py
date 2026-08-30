import pandas as pd
from gors_engine import RSI_EXIT, RSI_FULL_EXIT, calculate_rsi_exit_actions

def _panel():
    idx=pd.bdate_range("2025-01-01",periods=40)
    return pd.DataFrame({"ETF":[100.0]*len(idx)},index=idx)

def test_rsi_threshold_constants():
    assert RSI_EXIT==85
    assert RSI_FULL_EXIT==100

def test_rsi_85_sells_half(monkeypatch):
    panel=_panel(); cutoff=panel.index[-1]
    monkeypatch.setattr("gors_engine.rsi",lambda s:pd.Series(85.0,index=s.index))
    actions=calculate_rsi_exit_actions(panel,{"ETF":10},cutoff)
    assert actions[0]["Action"]=="SELL_HALF"
    assert actions[0]["Quantity"]==5

def test_rsi_100_exits_all(monkeypatch):
    panel=_panel(); cutoff=panel.index[-1]
    monkeypatch.setattr("gors_engine.rsi",lambda s:pd.Series(100.0,index=s.index))
    actions=calculate_rsi_exit_actions(panel,{"ETF":10},cutoff)
    assert actions[0]["Action"]=="SELL_ALL"
    assert actions[0]["Quantity"]==10
