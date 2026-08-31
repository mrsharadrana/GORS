from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "GORS_APP_PROD" / "requirements.txt"


def test_authlib_is_pinned_for_streamlit_oidc():
    lines = REQUIREMENTS.read_text(encoding="utf-8").splitlines()
    assert "Authlib==1.8.0" in lines
