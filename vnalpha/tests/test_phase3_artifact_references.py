from __future__ import annotations

import duckdb
import pytest

from vnalpha.assistant.groundedness import GroundednessResult
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan, ToolPlanStep
from vnalpha.assistant.policy import ResearchPolicyResult
from vnalpha.assistant.research_audit import (
    list_research_answer_audits,
    persist_research_answer_audit,
)
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.tools.research_intelligence import (
    deep_symbol_analysis,
    generate_shortlist,
    get_setup_history,
    summarize_watchlist_deep,
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


def test_artifact_reference_builder_adds_only_confirmed_unique_refs() -> None:
    from vnalpha.tools.artifact_references import ArtifactReferenceBuilder

    # Given: the same persisted score is confirmed twice and a sector row is absent.
    builder = ArtifactReferenceBuilder()
    builder.add_if_present("candidate_score", "FPT:2026-07-10", True)
    builder.add_if_present("candidate_score", "FPT:2026-07-10", True)
    builder.add_if_present("sector_strength_snapshot", "2026-07-10", False)

    # When: callers materialize the output reference list.
    refs = builder.build()

    # Then: only the unique confirmed persisted reference is emitted.
    assert refs == ["candidate_score:FPT:2026-07-10"]


@pytest.mark.parametrize(
    ("tool_case", "expected_missing"),
    [
        ("deep", "candidate_score"),
        ("watchlist", "daily_watchlist"),
        ("shortlist", "daily_watchlist"),
        ("setup", "setup_type_performance"),
    ],
)
def test_absent_artifact_matrix_emits_no_reference(
    tool_case: str, expected_missing: str
) -> None:
    # Given: the warehouse contains no persisted research artifacts.
    conn = _empty_conn()

    # When: each research tool is asked for an explicit date.
    match tool_case:
        case "deep":
            output = deep_symbol_analysis(conn, "FPT", "2026-07-10")
        case "watchlist":
            output = summarize_watchlist_deep(conn, "2026-07-10")
        case "shortlist":
            output = generate_shortlist(conn, "2026-07-10")
        case "setup":
            output = get_setup_history(
                conn,
                "MOMENTUM_CONTINUATION",
                date="2026-07-10",
            )
        case unreachable:
            raise AssertionError(unreachable)

    # Then: absence is disclosed and cannot produce a logical artifact ref.
    data = output.data
    assert isinstance(data, dict)
    assert data["artifact_refs"] == []
    assert expected_missing in data["missing_data"]


def test_shortlist_without_sector_snapshot_discloses_defaulted_component() -> None:
    # Given: a persisted watchlist candidate exists without any sector snapshot row.
    conn = _watchlist_without_sector()

    # When: deterministic shortlist generation evaluates the optional sector component.
    output = generate_shortlist(conn, "2026-07-10")

    # Then: watchlist lineage remains, sector lineage is omitted, and absence is explicit.
    data = output.data
    assert isinstance(data, dict)
    assert data["artifact_refs"] == ["daily_watchlist:2026-07-10"]
    assert "sector_strength_snapshot" in data["missing_data"]
    assert any("sector component defaulted" in item.lower() for item in data["caveats"])


def test_deep_symbol_without_sector_snapshot_discloses_missing_artifact() -> None:
    conn = _watchlist_without_sector()

    from vnalpha.data_availability.deep_readiness_models import ContextRequirement

    output = deep_symbol_analysis(
        conn,
        "FPT",
        "2026-07-10",
        sector_strength_requirement=ContextRequirement.REQUIRED,
    )

    data = output.data
    assert isinstance(data, dict)
    assert "sector_strength_snapshot" in data["missing_data"]
    assert all(
        not ref.startswith("sector_strength_snapshot:") for ref in data["artifact_refs"]
    )
    assert any(
        "sector strength snapshot" in caveat.lower() for caveat in data["caveats"]
    )


def test_filtered_shortlist_preserves_persisted_watchlist_reference() -> None:
    # Given: a persisted watchlist exists but no candidate clears a stricter threshold.
    conn = _watchlist_without_sector()

    # When: shortlist generation filters every persisted candidate.
    output = generate_shortlist(conn, "2026-07-10", min_score=0.95)

    # Then: watchlist lineage remains valid while candidate absence is disclosed.
    data = output.data
    assert isinstance(data, dict)
    assert "daily_watchlist:2026-07-10" in data["artifact_refs"]
    assert "daily_watchlist" not in data["missing_data"]
    assert "eligible_watchlist_candidates" in data["missing_data"]


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
