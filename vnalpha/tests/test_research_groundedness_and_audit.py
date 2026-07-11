from __future__ import annotations

import duckdb
import pytest

from vnalpha.assistant.groundedness import (
    GroundednessResult,
    validate_research_answer,
    validate_tool_grounding,
)
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan, ToolPlanStep
from vnalpha.assistant.research_audit import (
    list_research_answer_audits,
    persist_research_answer_audit,
)
from vnalpha.warehouse.assistant_repo import create_assistant_session
from vnalpha.warehouse.migrations import run_migrations


def _shortlist_plan() -> AssistantPlan:
    return AssistantPlan(
        intent="generate_shortlist",
        steps=[
            ToolPlanStep(
                step_id="shortlist-1",
                tool_name="shortlist.generate",
                arguments={"date": "2026-07-01", "limit": 5},
                purpose="research shortlist",
                required_permission="READ_WATCHLIST",
            )
        ],
        required_artifacts=["daily_watchlist", "candidate_score"],
    )


def _shortlist_outputs(*, status: str = "READY") -> dict:
    missing = ["matching candidates"] if status != "READY" else []
    return {
        "shortlist-1": {
            "data": {
                "status": status,
                "as_of_date": "2026-07-01",
                "methodology": {"version": "v1"},
                "candidates": [
                    {
                        "symbol": "FPT",
                        "research_rank": 1,
                        "shortlist_score": 0.81,
                        "artifact_refs": ["candidate_score:FPT:2026-07-01"],
                    }
                ]
                if status == "READY"
                else [],
                "artifact_refs": ["daily_watchlist:2026-07-01"],
                "freshness": {"watchlist_date": "2026-07-01"},
                "caveats": ["Research prioritization requires human review."],
                "missing_data": missing,
            },
            "summary": "Research shortlist payload.",
            "warnings": [],
        }
    }


def test_groundedness_passes_structured_research_answer() -> None:
    plan = _shortlist_plan()
    outputs = _shortlist_outputs()
    answer = AssistantAnswer(
        summary="Research shortlist: FPT remains first for evidence review.",
        basis="Based on shortlist_score and persisted candidate data.",
        risks_caveats="Caveat: fresh data and human confirmation are required.",
        tool_trace_summary="Used shortlist.generate.",
        missing_data=[],
    )

    result = validate_research_answer(plan, outputs, answer)

    assert result.passed
    assert result.policy_status == "PASS"
    assert "shortlist.generate" in result.tools_used
    assert "daily_watchlist:2026-07-01" in result.artifact_refs
    assert result.dataset_freshness


def test_groundedness_rejects_execution_wording() -> None:
    plan = _shortlist_plan()
    answer = AssistantAnswer(
        summary="Buy FPT now.",
        basis="Based on rank 1.",
        risks_caveats="Caveat: research only.",
        tool_trace_summary="Used shortlist.generate.",
        missing_data=[],
    )

    result = validate_research_answer(plan, _shortlist_outputs(), answer)

    assert not result.passed
    assert result.policy_status == "FAIL"
    assert any("execution-oriented" in issue for issue in result.issues)


def test_groundedness_requires_missing_data_disclosure() -> None:
    plan = _shortlist_plan()
    outputs = _shortlist_outputs(status="UNAVAILABLE")
    answer = AssistantAnswer(
        summary="Research shortlist is unavailable.",
        basis="No candidates were returned.",
        risks_caveats="Caveat: no persisted candidates are available.",
        tool_trace_summary="Used shortlist.generate.",
        missing_data=[],
    )

    result = validate_research_answer(plan, outputs, answer)

    assert not result.passed
    assert any("does not disclose" in issue for issue in result.issues)


def test_pre_synthesis_grounding_rejects_missing_required_key() -> None:
    plan = _shortlist_plan()
    outputs = _shortlist_outputs()
    del outputs["shortlist-1"]["data"]["methodology"]

    result = validate_tool_grounding(plan, outputs)

    assert result.status == "FAIL"
    assert any("methodology" in issue for issue in result.issues)


def test_research_answer_audit_persists_required_metadata() -> None:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    session_id = create_assistant_session(
        conn,
        surface="test",
        user_prompt="Create a research shortlist",
    )
    plan = _shortlist_plan()
    outputs = _shortlist_outputs()
    answer = AssistantAnswer(
        summary="Research shortlist: FPT remains first for review.",
        basis="Based on persisted shortlist_score.",
        risks_caveats="Caveat: fresh data and human confirmation are required.",
        tool_trace_summary="Used shortlist.generate.",
        missing_data=[],
    )
    groundedness = GroundednessResult(
        status="PASS",
        tools_used=("shortlist.generate",),
        artifact_refs=("daily_watchlist:2026-07-01",),
        dataset_freshness={"watchlist_date": "2026-07-01"},
        policy_status="PASS",
    )

    audit_id = persist_research_answer_audit(
        conn,
        assistant_session_id=session_id,
        plan=plan,
        tool_outputs=outputs,
        answer=answer,
        groundedness=groundedness,
    )
    records = list_research_answer_audits(conn)

    assert records[0]["research_answer_audit_id"] == audit_id
    assert records[0]["intent"] == "generate_shortlist"
    assert records[0]["tools"] == ["shortlist.generate"]
    assert records[0]["artifact_refs"] == ["daily_watchlist:2026-07-01"]
    assert records[0]["groundedness_status"] == "PASS"
    assert records[0]["policy_status"] == "PASS"
    assert records[0]["caveats"]
    conn.close()
