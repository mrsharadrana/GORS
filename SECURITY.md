# Security Policy

## Reporting a vulnerability

Please do not disclose security vulnerabilities in public issues, pull requests, workflow logs, or discussions.

Report suspected vulnerabilities privately to the repository owner through GitHub's private security reporting mechanism, if enabled. If private reporting is unavailable, contact the repository owner directly through GitHub before disclosing the issue publicly.

## Secrets policy

GORS must never commit passwords, API keys, OAuth client secrets, database credentials, private keys, or other production credentials to source control.

Production credentials are supplied through GitHub Actions Secrets and Streamlit Secrets. Workflow logs must never print secret values.

If a credential is accidentally committed, treat it as compromised: revoke or rotate it immediately, remove it from the repository, and review the affected service for unauthorized use.

## Supported versions

Only the current `main` branch is considered actively maintained for security fixes.
