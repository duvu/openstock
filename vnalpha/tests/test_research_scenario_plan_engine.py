from __future__ import annotations

from datetime import date, timedelta

import duckdb

from vnalpha.commands.handlers.research_plan import _scenario_panels, _scenario_tables
from vnalpha.research_models import ResearchModelsRepository
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.tools.research_intelligence import generate_research_scenario
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import save_candidate_score


def _scenario_connection(
    *, with_bars: bool = True, risk_flags: list[str] | None = None
) -> tuple[duckdb.DuckDBPyConnection, str]:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    as_of_date = date(2026, 7, 10)
    date_text = as_of_date.isoformat()
    save_candidate_score(
        conn,
        "FPT",
        date_text,
        {
            "score": 0.82,
            "candidate_class": "STRONG_CANDIDATE",
            "setup_type": "ACCUMULATION_BASE",
            "trend_score": 0.8,
            "relative_strength_score": 0.7,
            "volume_score": 0.6,
            "base_score": 0.5,
            "breakout_score": 0.4,
            "risk_quality_score": 0.9,
            "risk_flags": risk_flags or [],
            "rule_outcomes": {},
            "scoring_policy_id": BASELINE_SCORING_POLICY.policy_id,
            "scoring_policy_version": BASELINE_SCORING_POLICY.version,
            "scoring_policy_hash": BASELINE_SCORING_POLICY.payload_hash,
            "scoring_policy_status": BASELINE_SCORING_POLICY.lifecycle_status.value,
        },
    )
    if with_bars:
        for offset in range(25):
            bar_date = as_of_date - timedelta(days=offset)
            close = 100.0 - offset / 10
            conn.execute(
                "INSERT INTO canonical_ohlcv "
                "(symbol, time, interval, open, high, low, close, volume, "
                "selected_provider, quality_status) "
                "VALUES (?, ?, '1D', ?, ?, ?, ?, 1000000, 'test', 'PASS')",
                ["FPT", bar_date, close - 0.5, close + 2.0, close - 2.0, close],
            )
    return conn, date_text


def test_scenario_plan_persists_linked_research_artifacts() -> None:
    conn, as_of_date = _scenario_connection()
    try:
        output = generate_research_scenario(conn, "FPT", date=as_of_date)
        data = output.data

        assert data["policy_classification"] == "RESEARCH_ONLY"
        assert {branch["name"] for branch in data["scenarios"]} == {
            "base_case",
            "confirmation_case",
            "failed_confirmation_case",
            "low_quality_drift_case",
        }
        assert data["scenario_tree"]
        for branch in data["scenario_tree"].values():
            assert {"condition", "evidence_to_watch", "risk_context", "caveat"} <= set(
                branch
            )
        assert "future confirmation" in data["risk_reward_estimate"]
        assert "not a recommendation" in data["risk_reward_estimate"]
        assert "not an execution instruction" in data["risk_reward_estimate"]
        risk_panel = next(
            panel
            for panel in _scenario_panels(data)
            if panel.title == "Risk and checklist"
        )
        assert risk_panel.content["confidence"] == f"{data['confidence']:.3f}"
        assert risk_panel.content["estimate"] == data["risk_reward_estimate"]
        scenario_table = _scenario_tables(data)[0]
        assert {"evidence_to_watch", "risk_context", "caveat"} <= {
            column.name for column in scenario_table.columns
        }

        plan = ResearchModelsRepository(conn).get_research_scenario_plan(
            data["scenario_plan_id"]
        )

        assert plan is not None
        assert plan.as_of_date.isoformat() == as_of_date
        assert plan.lineage["deep_symbol_analysis_ref"] == (
            f"analysis.deep_symbol:FPT:{as_of_date}"
        )
        assert plan.lineage["symbol_level_snapshot_ref"].startswith("levels-")
        assert plan.lineage["setup_evidence_snapshot_ref"].startswith("evidence-")
        assert plan.correlation_id
        assert (
            ResearchModelsRepository(conn).get_symbol_level_snapshot(
                plan.lineage["symbol_level_snapshot_ref"]
            )
            is not None
        )
        assert (
            ResearchModelsRepository(conn).get_setup_evidence_snapshot(
                plan.lineage["setup_evidence_snapshot_ref"]
            )
            is not None
        )
        assert (
            "research_scenario_plan:" + data["scenario_plan_id"]
            in data["artifact_refs"]
        )
    finally:
        conn.close()
