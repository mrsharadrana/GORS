# GORS_APP_PROD — Daily Snapshot Reuse

## Daily workflow

1. Start GORS.
2. GORS automatically loads the latest verified Kite holdings snapshot from SQLite.
3. Update **Kite Available Cash** in the left panel only when the actual Kite cash has changed.
4. Review Block 2 reconciliation.
5. Review Block 3 order ticket.
6. Verify live Kite prices/funds and execute manually if required.

## When to upload Holdings.csv

Upload a fresh Kite Holdings CSV **only when the actual Kite portfolio changes**, such as after a BUY/SELL or another portfolio change that should become the new broker snapshot.

If there is no trade for six days, you do **not** need to upload six CSV files. GORS keeps using the latest saved Kite snapshot from SQLite.

If the same CSV is uploaded again, GORS detects the matching checksum and does not create a duplicate snapshot.

## Data ownership

- **SQLite:** verified facts and history.
- **Python:** GORS strategy and decision calculations.
- **Kite:** actual portfolio and execution truth.
- **UI:** display and manual controls.

The database is persistent at `~/GORS/data/gors.db`. Existing historical data is not deleted by normal application startup.

## Start

```bash
cd ~/Downloads/GORS_APP_PROD
./run_GORS_APP_PROD.sh
```
