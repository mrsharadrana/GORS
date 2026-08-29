# GORS_APP_PROD — Frozen HR5 Manual Trading Dashboard

## Daily workflow

1. Start GORS after market close.
2. Open **Rotation Signal**.
3. Confirm the **Signal date** is the latest completed common trading date across the required ETF universe.
4. Review portfolio state: RISK ON/OFF, target exposure, actual exposure, portfolio equity, drawdown and last Kite update.
5. Review **TODAY'S ACTION**.
6. Execute any BUY/SELL/RISK-OFF/RISK-ON instruction manually in Kite only after verifying live Kite prices and funds.

## Frozen strategy configuration

- HoldRank = 5
- Top selection = 3
- RSI(14) thresholds = 85 / 100
- Drawdown trigger = 8%
- Recovery = 75% of the drawdown trigger
- Risk-off exposure = 50%
- Transaction cost assumption = 0.25%

The GORS Python calculation engine is the source of truth for signals. The UI displays the signal and manual trading quantities; it does not optimize parameters or introduce discretionary signals.

## When to upload Holdings.csv

Upload a fresh Kite Holdings CSV **only when the actual Kite portfolio changes**, such as after a BUY/SELL or another portfolio change that should become the new broker snapshot.

If there is no trade for six days, you do **not** need to upload six CSV files. GORS keeps using the latest saved Kite snapshot from SQLite.

If the same CSV is uploaded again, GORS detects the matching checksum and does not create a duplicate snapshot.

## Data ownership

- **SQLite:** verified facts and history.
- **Python GORS engine:** frozen HR5 signal, risk state and manual action calculations.
- **Kite:** actual portfolio and execution truth.
- **UI:** display and manual controls only.

The database is persistent at `~/GORS/data/gors.db`. Existing historical data is not deleted by normal application startup.

## Start

```bash
cd ~/Downloads/GORS_APP_PROD
./run_GORS_APP_PROD.sh
```
