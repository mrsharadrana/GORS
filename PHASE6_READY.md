Phase 6 data reliability implementation is complete on feature/phase6-data-reliability.

The existing weekday 4 PM IST refresh workflow is preserved. Market data is validated before acceptance, MON100 correction is gated, and validated cache metadata is recorded. Regression tests cover invalid market data and the refresh contract.
