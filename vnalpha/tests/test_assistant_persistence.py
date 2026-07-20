"""Tests for Phase 5.9 assistant session and LLM trace persistence."""

from __future__ import annotations

import json

import duckdb
import pytest

from vnalpha.assistant.models import (
    AssistantPlan,
    AssistantRequest,
    IntentResult,
    PreparedAssistantTurn,
    PromptPersistenceRecord,
    ToolPlanStep,
    plan_hash,
)
from vnalpha.warehouse.assistant_repo import (
    create_assistant_session,
    finish_assistant_session,
    mark_assistant_session_prepared,
    persist_prepared_turn,
)
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


def test_migrations_create_assistant_and_llm_tables(conn):
    tables = {t[0] for t in conn.execute("SHOW TABLES").fetchall()}
    assert "assistant_session" in tables
    assert "llm_trace" in tables


def test_migrations_idempotent(conn):
    run_migrations(conn=conn)  # second run
    tables = conn.execute("SHOW TABLES").fetchall()
    assert len(tables) == 74  # + fundamental_fact (issue #257)


def test_assistant_session_projections_redact_nested_dynamic_content(conn):
    private_fragment = "SESSION_SECRET_37"
    hostile = (
        f"password={private_fragment} "
        "\x1b]8;;https://example.invalid\x1b\\click\x1b]8;;\x1b\\"
    )
    session_id = create_assistant_session(
        conn,
        surface="test",
        user_prompt=hostile,
        prompt=PromptPersistenceRecord(
            prompt_text=hostile,
            prompt_summary=hostile,
            prompt_hash="hash",
            prompt_chars=len(hostile),
            workspace_context_ref=hostile,
            chat_context_ref=hostile,
            raw_stored=True,
        ),
    )

    mark_assistant_session_prepared(
        conn,
        session_id,
        intent="scan_candidates",
        plan={"steps": [{"arguments": {"note": hostile}}]},
    )
    finish_assistant_session(
        conn,
        session_id,
        status="SUCCESS",
        plan={"steps": [{"arguments": {"note": hostile}}]},
        answer={"summary": hostile, "nested": {"warning": hostile}},
        refusal_reason=hostile,
        error={"message": hostile},
    )

    row = conn.execute(
        "SELECT user_prompt, prompt_text, prompt_summary, workspace_context_ref, "
        "chat_context_ref, plan_json, answer_json, refusal_reason, error_json "
        "FROM assistant_session WHERE assistant_session_id = ?",
        [session_id],
    ).fetchone()
    serialized = " ".join(str(value) for value in row)
    assert private_fragment not in serialized
    assert "\x1b]8;" not in serialized
    assert "[REDACTED]" in serialized


def test_prepared_turn_projection_redacts_request_intent_and_plan(conn):
    private_fragment = "PREPARED_SECRET_53"
    hostile = (
        f"authorization=Bearer {private_fragment} "
        "\x1b]8;;https://example.invalid\x1b\\click\x1b]8;;\x1b\\"
    )
    session_id = create_assistant_session(
        conn,
        surface="test",
        user_prompt="prompt summary",
    )
    plan = AssistantPlan(
        intent="scan_candidates",
        steps=[
            ToolPlanStep(
                step_id="step-1",
                tool_name="watchlist.scan",
                arguments={"note": hostile},
                purpose=hostile,
                required_permission="READ_WATCHLIST",
            )
        ],
    )
    turn = PreparedAssistantTurn(
        prepared_turn_id="turn-redaction",
        assistant_session_id=session_id,
        request=AssistantRequest(current_user_prompt=hostile),
        intent_result=IntentResult(
            intent="scan_candidates",
            confidence=1.0,
            entities={"note": hostile},
        ),
        plan=plan,
        plan_hash=plan_hash(plan),
        policy_status="PASS",
        created_at="2026-07-19T00:00:00+00:00",
    )

    persist_prepared_turn(conn, turn)

    row = conn.execute(
        "SELECT request_json, intent_json, plan_json FROM prepared_assistant_turn "
        "WHERE prepared_turn_id = 'turn-redaction'"
    ).fetchone()
    decoded = [json.loads(value) for value in row]
    serialized = json.dumps(decoded)
    assert private_fragment not in serialized
    assert "\\u001b]8;" not in serialized
    assert "[REDACTED]" in serialized
