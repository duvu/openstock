from __future__ import annotations

import duckdb

from vnalpha.assistant.groundedness import GroundednessResult
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan, ToolPlanStep
from vnalpha.assistant.policy import ResearchPolicyResult
from vnalpha.assistant.research_audit import (
    list_research_answer_audits,
    persist_research_answer_audit,
)
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.tools.research_intelligence import (
    generate_shortlist,
)
from vnalpha.warehouse.migrations import run_migrations


def _empty_conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect()
    run_migrations(conn=conn)
    return conn


def _watchlist_without_sector() -> duckdb.DuckDBPyConnection:
    conn = _empty_conn()
    conn.execute(
        """
        INSERT INTO symbol_master (symbol, sector, is_active)
        VALUES ('FPT', 'Technology', TRUE)
        """
    )
    conn.execute(
        """
        INSERT INTO candidate_score
        (symbol, date, score, candidate_class, setup_type, risk_quality_score,
         evidence_json, risk_flags_json, lineage_json, scoring_policy_id,
         scoring_policy_version, scoring_policy_hash, scoring_policy_status)
        VALUES ('FPT', '2026-07-10', 0.8, 'WATCH_CANDIDATE',
                'MOMENTUM_CONTINUATION', 0.9,
                '{"risk_quality_score": 0.9}', '[]', '{}', ?, ?, ?, ?)
        """,
        [
            BASELINE_SCORING_POLICY.policy_id,
            BASELINE_SCORING_POLICY.version,
            BASELINE_SCORING_POLICY.payload_hash,
            BASELINE_SCORING_POLICY.lifecycle_status.value,
        ],
    )
    conn.execute(
        """
        INSERT INTO daily_watchlist
        (date, rank, symbol, score, candidate_class, setup_type,
         risk_flags_json, lineage_json, scoring_policy_id,
         scoring_policy_version, scoring_policy_hash, scoring_policy_status)
        VALUES ('2026-07-10', 1, 'FPT', 0.8, 'WATCH_CANDIDATE',
                'MOMENTUM_CONTINUATION', '[]', '{}', ?, ?, ?, ?)
        """,
        [
            BASELINE_SCORING_POLICY.policy_id,
            BASELINE_SCORING_POLICY.version,
            BASELINE_SCORING_POLICY.payload_hash,
            BASELINE_SCORING_POLICY.lifecycle_status.value,
        ],
    )
    return conn


def _watchlist_with_duplicate_symbol() -> duckdb.DuckDBPyConnection:
    conn = _watchlist_without_sector()
    conn.execute(
        """
        INSERT INTO daily_watchlist
        (date, rank, symbol, score, candidate_class, setup_type,
         risk_flags_json, lineage_json, scoring_policy_id,
         scoring_policy_version, scoring_policy_hash, scoring_policy_status)
        VALUES ('2026-07-10', 2, 'FPT', 0.6, 'WATCH_CANDIDATE',
                'MOMENTUM_CONTINUATION', '[]', '{}', ?, ?, ?, ?)
        """,
        [
            BASELINE_SCORING_POLICY.policy_id,
            BASELINE_SCORING_POLICY.version,
            BASELINE_SCORING_POLICY.payload_hash,
            BASELINE_SCORING_POLICY.lifecycle_status.value,
        ],
    )
    return conn


def test_shortlist_refs_remain_integral_through_research_answer_audit() -> None:
    # Given: shortlist output confirms a watchlist but no sector snapshot.
    conn = _watchlist_without_sector()
    output = generate_shortlist(conn, "2026-07-10")
    step = ToolPlanStep(
        step_id="step_1",
        tool_name="shortlist.generate",
        arguments={"date": "2026-07-10"},
        purpose="Build research shortlist",
        required_permission="READ_WATCHLIST",
    )
    plan = AssistantPlan(intent="generate_shortlist", steps=[step])
    tool_outputs = {
        step.step_id: {
            "data": output.data,
            "summary": output.summary,
            "warnings": output.warnings,
        }
    }
    answer = AssistantAnswer(
        summary="Research shortlist from persisted evidence.",
        basis="Deterministic shortlist tool.",
        risks_caveats="Research-only; sector context is unavailable.",
        tool_trace_summary="shortlist.generate completed.",
        missing_data=["sector_strength_snapshot"],
        grounded_source_refs=["daily_watchlist:2026-07-10"],
    )

    # When: the validated answer audit is persisted and loaded.
    persist_research_answer_audit(
        conn,
        assistant_session_id="session-1",
        plan=plan,
        tool_outputs=tool_outputs,
        answer=answer,
        groundedness=GroundednessResult(status="PASS"),
        policy=ResearchPolicyResult(status="PASS", disclaimer_present=True),
    )
    audits = list_research_answer_audits(conn)

    # Then: the audit contains exactly the query-backed tool reference.
    assert audits[0]["artifact_refs"] == ["daily_watchlist:2026-07-10"]
