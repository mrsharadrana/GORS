from pathlib import Path

from GORS_APP_PROD.gors_engine import TICKERS
from GORS_APP_PROD.market_data_reliability import validate_market_data


def test_refresh_workflow_is_weekday_4pm_ist():
    workflow = Path('.github/workflows/gors-market-refresh.yml').read_text(encoding='utf-8')
    assert "0 16 * * 1-5" in workflow
    assert "timezone: 'Asia/Kolkata'" in workflow


def test_refresh_uses_frozen_universe():
    assert set(TICKERS) == {"MOM30", "MOM50", "MIDMOM", "SMALLMOM", "MON100", "NIFTY", "GOLD", "SILVER"}


def test_empty_refresh_is_rejected():
    import pandas as pd
    ok, reason = validate_market_data(pd.DataFrame(), list(TICKERS))
    assert not ok
    assert "empty" in reason
