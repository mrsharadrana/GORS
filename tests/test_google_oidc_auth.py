from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "GORS_APP_PROD" / "app.py"
AUTH = ROOT / "GORS_APP_PROD" / "auth.py"


def test_google_oidc_guard_is_wired_before_db_initialization():
    source = APP.read_text(encoding="utf-8")
    assert "from auth import logout_button, require_google_login" in source
    guard = source.index("require_google_login()")
    init_db = source.index("init_db()")
    assert guard < init_db


def test_auth_module_uses_native_default_streamlit_oidc_and_logout():
    source = AUTH.read_text(encoding="utf-8")
    assert "st.login()" in source
    assert 'st.login("google")' not in source
    assert "st.logout()" in source
    assert "st.user.is_logged_in" in source


def test_no_oauth_credentials_are_committed():
    auth_source = AUTH.read_text(encoding="utf-8")
    app_source = APP.read_text(encoding="utf-8")
    combined = auth_source + "\n" + app_source
    forbidden = ("client_secret", "client_secret.json", "GOOGLE_CLIENT_SECRET")
    assert not any(token in combined for token in forbidden)


def test_gors_keeps_manual_execution_boundary():
    source = APP.read_text(encoding="utf-8").lower()
    forbidden = ("place_order(", "modify_order(", "cancel_order(")
    assert not any(token in source for token in forbidden)
