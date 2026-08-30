import pandas as pd

from gors_engine import HOLD_RANK, TOP_N, monthly_holdrank_selection


def test_holdrank5_keeps_existing_rank_4_and_5(monkeypatch):
    idx = pd.to_datetime(["2026-01-30", "2026-02-27"])
    panel = pd.DataFrame(1.0, index=idx, columns=["A", "B", "C", "D", "E"])
    rankings = {
        idx[0]: {"A": .50, "B": .40, "C": .30, "D": .20, "E": .10},
        idx[1]: {"D": .60, "E": .50, "A": .40, "B": .30, "C": .20},
    }
    monkeypatch.setattr("gors_engine.eligible", lambda panel, date: rankings[pd.Timestamp(date)])
    selected, rebalance_date, _, ranks, _ = monthly_holdrank_selection(panel, idx[1])
    assert HOLD_RANK == 5
    assert TOP_N == 3
    assert rebalance_date == idx[1]
    assert ranks["A"] == 3
    assert ranks["B"] == 4
    assert ranks["C"] == 5
    assert selected == ["A", "B", "C"]


def test_holdrank5_replaces_existing_rank_6(monkeypatch):
    idx = pd.to_datetime(["2026-01-30", "2026-02-27"])
    panel = pd.DataFrame(1.0, index=idx, columns=["A", "B", "C", "D", "E", "F"])
    rankings = {
        idx[0]: {"A": .50, "B": .40, "C": .30, "D": .20, "E": .10, "F": .05},
        idx[1]: {"D": .60, "E": .50, "A": .40, "C": .30, "F": .20, "B": .10},
    }
    monkeypatch.setattr("gors_engine.eligible", lambda panel, date: rankings[pd.Timestamp(date)])
    selected, _, _, ranks, history = monthly_holdrank_selection(panel, idx[1])
    assert ranks["B"] == 6
    assert ranks["C"] == 4
    assert "B" not in selected
    assert "C" in selected
    assert selected == ["A", "C", "D"]
    assert any(x["ETF"] == "B" and x["Action"] == "REPLACE" for x in history)
