from __future__ import annotations

import duckdb

from vnalpha.warehouse.migrations import run_migrations


def test_research_scenario_plan_persists_artifact_links_and_correlation() -> None:
    from vnalpha.warehouse.repositories import (
        get_research_scenario_plan,
        save_research_scenario_plan,
    )

    conn = duckdb.connect(":memory:")
    run_migrations(conn)
    plan = {
        "scenario_plan_id": "plan-1",
        "symbol": "FPT",
        "as_of_date": "2025-01-31",
        "current_setup": {"trend": "UPTREND"},
        "key_levels": [],
        "confirmation_conditions": [],
        "invalidation_conditions": [],
        "scenario_tree": {},
        "risk_reward_estimate": None,
        "checklist": [],
        "confidence": 0.5,
        "caveats": [],
        "research_only_language": (
            "Research-only context; not an execution instruction; requires future confirmation."
        ),
        "artifact_references": {
            "deep_analysis": {"symbol": "FPT", "date": "2025-01-31"},
            "level_snapshot": {"symbol": "FPT", "date": "2025-01-31"},
            "evidence_snapshot": {"symbol": "FPT", "date": "2025-01-31"},
        },
        "correlation_id": "corr-1",
    }

    save_research_scenario_plan(conn, plan)

    stored = get_research_scenario_plan(conn, "FPT", "2025-01-31")
    assert stored is not None
    assert stored["correlation_id"] == "corr-1"
    assert stored["artifact_references"] == plan["artifact_references"]
