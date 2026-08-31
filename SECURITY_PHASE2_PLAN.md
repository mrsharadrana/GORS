# Phase 2 — GitHub Actions Hardening

Planned hardening:
- Explicit read-only repository permissions on workflows.
- Scope production database secret to the single refresh step that requires it.
- Standardize maintained checkout/setup-python action versions.
- Preserve existing GORS behavior and tests.
