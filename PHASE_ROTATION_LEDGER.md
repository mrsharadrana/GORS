# ETF Rotation Ledger

GORS History reports only actual Top-3 ETF membership changes from the persisted `decision_history` records.

- Re-ordering the same three ETFs is not a rotation.
- A new ETF entering Top 3 and an ETF leaving Top 3 is recorded as a membership change.
- The page shows the rotation date, previous Top 3, new Top 3, added ETF(s), removed ETF(s), and risk state.
- Strategy calculation and broker execution are unchanged.
