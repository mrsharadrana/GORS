# Phase 6 — Google OIDC

The Streamlit dashboard is protected by native Google OIDC authentication.

## Streamlit deployment configuration

Configure the Google OIDC provider in Streamlit Secrets. Do not commit the client ID, client secret, or redirect credentials to GitHub.

The application calls `st.login("google")` for unauthenticated sessions and exposes `st.logout()` for authenticated users.
