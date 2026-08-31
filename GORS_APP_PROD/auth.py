"""Authentication guard for the GORS Streamlit application.

Google OIDC configuration belongs in Streamlit Secrets, never in source control.
"""

import streamlit as st


def require_google_login() -> None:
    """Require an authenticated Google OIDC session before rendering the app."""
    if not st.user.is_logged_in:
        st.login("google")
        st.stop()


def logout_button() -> None:
    """Render a logout control for authenticated users."""
    if st.user.is_logged_in:
        if st.sidebar.button("Log out", use_container_width=True):
            st.logout()
