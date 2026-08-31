from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_workflow(name):
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_market_refresh_has_read_only_permissions():
    workflow = read_workflow("gors-market-refresh.yml")
    assert "permissions:\n  contents: read" in workflow


def test_market_refresh_scopes_database_secret_to_refresh_step():
    workflow = read_workflow("gors-market-refresh.yml")
    # The secret must not be configured at job scope.
    assert "\n    env:\n      DATABASE_URL: ${{ secrets.DATABASE_URL }}" not in workflow
    # It must be scoped to the single refresh step that consumes it.
    assert "\n        env:\n          DATABASE_URL: ${{ secrets.DATABASE_URL }}" in workflow


def test_actions_use_node24_compatible_maintained_versions():
    refresh = read_workflow("gors-market-refresh.yml")
    tests = read_workflow("gors-tests.yml")
    for workflow in (refresh, tests):
        assert "actions/checkout@v5" in workflow
        assert "actions/setup-python@v6" in workflow
