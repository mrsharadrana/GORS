# Phase 2 validation

The Actions hardening regression suite verifies:

- Market refresh workflow has read-only repository permissions.
- DATABASE_URL is scoped only to the refresh command step.
- Test and refresh workflows use checkout v5 and setup-python v6.

The existing GORS engine and dashboard test suites remain part of CI.
