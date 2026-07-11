from __future__ import annotations

import duckdb

from vnalpha.warehouse.migrations import run_migrations


def test_scenario_plan_discloses_missing_level_data() -> None:
    from vnalpha.research_intelligence.scenario_plan import ScenarioPlanBuilder

    conn = duckdb.connect(":memory:")
    run_migrations(conn)
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, close, ma20, feature_data_status, lineage_json
        ) VALUES ('FPT', '2025-01-31', 120.0, 115.0, 'EXACT_DATE', '{}')
        """
    )

    plan = ScenarioPlanBuilder(conn).build("FPT", "2025-01-31")

    assert plan["key_levels"] == []
    assert any(
        "key level data is unavailable" in caveat.lower() for caveat in plan["caveats"]
    )
