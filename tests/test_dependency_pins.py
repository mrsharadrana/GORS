from pathlib import Path


EXPECTED = {
    "streamlit": "1.62.0",
    "pandas": "3.0.5",
    "numpy": "2.5.2",
    "yfinance": "1.7.0",
    "psycopg[binary]": "3.3.4",
}


def _requirements():
    path = Path(__file__).parents[1] / "GORS_APP_PROD" / "requirements.txt"
    result = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, version = line.split("==", 1)
        result[name] = version
    return result


def test_production_dependencies_are_exactly_pinned():
    assert _requirements() == EXPECTED
