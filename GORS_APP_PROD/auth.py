"""Authentication guard for the GORS Streamlit application.

Google OIDC configuration belongs in Streamlit Secrets, never in source control.
"""

import streamlit as st


def require_google_login() -> None:
    """Render a login control and stop before protected app content."""
    if not st.user.is_logged_in:
        st.button("Sign in with Google", type="primary", use_container_width=True, on_click=st.login)
        st.stop()


def logout_button() -> None:
    """Render a logout control for authenticated users."""
    if st.user.is_logged_in:
        st.sidebar.button("Log out", use_container_width=True, on_click=st.logout)
