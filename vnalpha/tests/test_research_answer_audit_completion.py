from __future__ import annotations

import json

import duckdb

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.groundedness import GroundednessResult
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
from vnalpha.assistant.policy import ResearchPolicyResult
from vnalpha.assistant.research_audit import (
    list_research_answer_audits,
    persist_research_answer_audit,
)
from vnalpha.warehouse.assistant_repo import create_assistant_session
from vnalpha.warehouse.migrations import run_migrations


def _intent_response() -> tuple[str, dict]:
    return (
        json.dumps(
            {
                "intent": "deep_analyze_symbol",
                "confidence": 0.99,
                "entities": {"symbol": "FPT", "date": "2026-07-10"},
                "needs_clarification": False,
                "clarification_question": None,
                "safety_flags": [],
            }
        ),
        {},
    )


def _answer_response() -> tuple[str, dict]:
    return (
        json.dumps(
            {
                "summary": "FPT has a persisted score of 0.75 for research review.",
                "basis": "Based on the deterministic deep-symbol payload.",
                "risks_caveats": (
                    "Research-only context; data freshness remains relevant."
                ),
                "tool_trace_summary": "analysis.deep_symbol completed.",
                "missing_data": [],
                "grounded_source_refs": [],
                "research_metadata": {},
            }
        ),
        {"prompt_tokens": 10, "completion_tokens": 20},
    )


def _tool_outputs(plan):
    step = next(s for s in plan.steps if s.tool_name == "analysis.deep_symbol")
    return {
        step.step_id: {
            "data": {
                "tool": "analysis.deep_symbol",
                "available": True,
                "symbol": "FPT",
                "as_of_date": "2026-07-10",
                "candidate": {
                    "score": 0.75,
                    "candidate_class": "WATCH_CANDIDATE",
                    "setup_type": "MOMENTUM_CONTINUATION",
                },
                "feature_context": {"close": 100.0, "ma20": 98.0},
                "levels": {"support_20d": 95.0, "resistance_20d": 105.0},
                "freshness": {"price_bar_date": "2026-07-10"},
                "lineage": {"source": "persisted warehouse"},
                "artifact_refs": ["candidate_score:FPT:2026-07-10"],
                "missing_data": [],
                "caveats": ["Research-only persisted context."],
            },
            "summary": "Persisted deep research context.",
            "warnings": [],
        }
    }


def test_migrations_create_research_answer_audit_table():
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)

    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = 'research_answer_audit'
        """
    ).fetchone()

    assert row == (1,)
    conn.close()


def test_assistant_app_persists_validated_research_answer_audit(monkeypatch):
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    fake = FakeLLMClient(responses=[_intent_response(), _answer_response()])

    def execute(_self, plan):
        return _tool_outputs(plan)

    monkeypatch.setattr(
        "vnalpha.assistant.executor.AssistantExecutor.execute",
        execute,
    )
    app = AssistantApp(conn, surface="test", llm_client=fake)

    answer, plan = app.ask(
        "Give me a deep research review of FPT.",
        date="2026-07-10",
    )

    assert plan.intent == "deep_analyze_symbol"
    audit_id = answer.research_metadata["research_answer_audit_id"]
    audits = list_research_answer_audits(conn)
    assert len(audits) == 1
    assert audits[0]["research_answer_audit_id"] == audit_id
    assert audits[0]["intent"] == "deep_analyze_symbol"
    # Provisioning now appears explicitly in the tool/audit trace (issue #163).
    assert audits[0]["tools"] == ["data.ensure_current_symbol", "analysis.deep_symbol"]
    assert audits[0]["artifact_refs"] == ["candidate_score:FPT:2026-07-10"]
    assert audits[0]["groundedness_status"] == "PASS"
    assert audits[0]["policy_status"] == "PASS"
    assert audits[0]["dataset_freshness"]

    session = conn.execute(
        "SELECT status, answer_json FROM assistant_session"
    ).fetchone()
    assert session[0] == "SUCCESS"
    persisted_answer = json.loads(session[1])
    assert persisted_answer["research_metadata"]["research_answer_audit_id"] == audit_id
    # Knowledge projection runs on the validated deep-analysis turn (issue #164);
    # here no artifacts are persisted so it projects nothing but still reports.
    assert "knowledge_projection" in answer.research_metadata
    conn.close()


def test_research_answer_audit_redacts_dynamic_caveats():
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    session_id = create_assistant_session(
        conn,
        surface="test",
        user_prompt="prompt summary",
    )
    private_fragment = "AUDIT_SECRET_49"
    hostile = (
        f"password={private_fragment} "
        "\x1b]8;;https://example.invalid\x1b\\click\x1b]8;;\x1b\\"
    )

    persist_research_answer_audit(
        conn,
        assistant_session_id=session_id,
        plan=AssistantPlan(intent="deep_analyze_symbol", steps=[]),
        tool_outputs={
            "step": {
                "data": {"caveats": [hostile]},
                "warnings": [hostile],
            }
        },
        answer=AssistantAnswer(
            summary="safe",
            basis="safe",
            risks_caveats=hostile,
            tool_trace_summary="safe",
        ),
        groundedness=GroundednessResult(status="PASS"),
        policy=ResearchPolicyResult(status="PASS", disclaimer_present=True),
    )

    caveats = json.dumps(list_research_answer_audits(conn)[0]["caveats"])
    assert private_fragment not in caveats
    assert "\\u001b]8;" not in caveats
    assert "[REDACTED]" in caveats
    conn.close()
