from importlib.metadata import version
from pathlib import Path


EXPECTED = {
    "streamlit": "1.62.0",
    "pandas": "3.0.5",
    "numpy": "2.5.2",
    "yfinance": "1.7.0",
    "psycopg": "3.3.4",
    "Authlib": "1.8.0",
    "httpx": "0.28.1",
}


def _requirements():
    path = Path(__file__).parents[1] / "GORS_APP_PROD" / "requirements.txt"
    result = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, pinned = line.split("==", 1)
        result[name.split("[", 1)[0]] = pinned
    return result


def test_production_dependencies_are_exactly_pinned():
    assert _requirements() == EXPECTED


def test_installed_production_dependencies_match_pins():
    for package, expected_version in EXPECTED.items():
        assert version(package) == expected_version
