from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from vnalpha.assistant.models import (
    PreparedAssistantTurn,
    PromptPersistenceRecord,
)
from vnalpha.core.text_safety import redact_structure, sanitize_text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump_redacted(value: object, *, sort_keys: bool = False) -> str:
    return json.dumps(
        redact_structure(value, parse_json_strings=True), sort_keys=sort_keys
    )


def create_assistant_session(
    conn,
    *,
    surface: str,
    user_prompt: str,
    intent: str | None = None,
    prompt: PromptPersistenceRecord | None = None,
) -> str:
    session_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO assistant_session
            (assistant_session_id, started_at, status, surface, user_prompt, intent,
             prompt_text, prompt_summary, prompt_hash, prompt_chars,
             workspace_context_ref, chat_context_ref, raw_stored)
        VALUES (?, ?, 'RUNNING', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            session_id,
            _now(),
            surface,
            sanitize_text(user_prompt),
            intent,
            sanitize_text(prompt.prompt_text)
            if prompt and prompt.prompt_text
            else None,
            sanitize_text(prompt.prompt_summary) if prompt else None,
            prompt.prompt_hash if prompt else None,
            prompt.prompt_chars if prompt else None,
            sanitize_text(prompt.workspace_context_ref)
            if prompt and prompt.workspace_context_ref
            else None,
            sanitize_text(prompt.chat_context_ref)
            if prompt and prompt.chat_context_ref
            else None,
            prompt.raw_stored if prompt else False,
        ],
    )
    return session_id


def finish_assistant_session(
    conn,
    session_id: str,
    *,
    status: str,
    intent: str | None = None,
    plan: dict | None = None,
    answer: dict | None = None,
    refusal_reason: str | None = None,
    error: dict | None = None,
) -> None:
    conn.execute(
        """
        UPDATE assistant_session SET
            finished_at = ?,
            status = ?,
            intent = COALESCE(?, intent),
            plan_json = ?,
            answer_json = ?,
            refusal_reason = ?,
            error_json = ?
        WHERE assistant_session_id = ?
        """,
        [
            _now(),
            status,
            intent,
            _dump_redacted(plan) if plan else None,
            _dump_redacted(answer) if answer else None,
            sanitize_text(refusal_reason) if refusal_reason else None,
            _dump_redacted(error) if error else None,
            session_id,
        ],
    )


def mark_assistant_session_prepared(
    conn,
    session_id: str,
    *,
    intent: str,
    plan: dict,
) -> None:
    conn.execute(
        """
        UPDATE assistant_session
        SET status = 'PREPARED', intent = ?, plan_json = ?
        WHERE assistant_session_id = ?
        """,
        [intent, _dump_redacted(plan, sort_keys=True), session_id],
    )


def list_assistant_sessions(conn, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        """
        SELECT assistant_session_id, started_at, finished_at, status, surface,
               user_prompt, intent, refusal_reason
        FROM assistant_session
        ORDER BY started_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    keys = [
        "assistant_session_id",
        "started_at",
        "finished_at",
        "status",
        "surface",
        "user_prompt",
        "intent",
        "refusal_reason",
    ]
    return [dict(zip(keys, row, strict=False)) for row in rows]


def create_llm_trace(
    conn,
    *,
    assistant_session_id: str,
    stage: str,
    model: str | None = None,
    input_summary: dict | None = None,
) -> str:
    trace_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO llm_trace
            (llm_trace_id, assistant_session_id, stage, model, started_at, status, input_summary_json)
        VALUES (?, ?, ?, ?, ?, 'RUNNING', ?)
        """,
        [
            trace_id,
            assistant_session_id,
            stage,
            sanitize_text(model) if model else None,
            _now(),
            _dump_redacted(input_summary) if input_summary else None,
        ],
    )
    return trace_id


def finish_llm_trace(
    conn,
    trace_id: str,
    *,
    status: str,
    output_summary: dict | None = None,
    usage: dict | None = None,
    error: dict | None = None,
    model: str | None = None,
) -> None:
    resolved_model = model or _model_from_usage(usage)
    conn.execute(
        """
        UPDATE llm_trace SET
            finished_at = ?,
            status = ?,
            model = COALESCE(?, model),
            output_summary_json = ?,
            usage_json = ?,
            error_json = ?
        WHERE llm_trace_id = ?
        """,
        [
            _now(),
            status,
            sanitize_text(resolved_model) if resolved_model else None,
            _dump_redacted(output_summary) if output_summary else None,
            _dump_redacted(usage) if usage else None,
            _dump_redacted(error) if error else None,
            trace_id,
        ],
    )


def _model_from_usage(usage: dict | None) -> str | None:
    if not isinstance(usage, dict):
        return None
    route_profile = usage.get("route_profile")
    if route_profile in {"small", "default", "reasoning", "long_context"}:
        return route_profile
    return None


def persist_prepared_turn(conn, turn: PreparedAssistantTurn) -> None:
    conn.execute(
        """
        INSERT INTO prepared_assistant_turn
            (prepared_turn_id, assistant_session_id, created_at, request_json,
             intent_json, plan_json, plan_hash, policy_status, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PREPARED')
        """,
        [
            turn.prepared_turn_id,
            turn.assistant_session_id,
            turn.created_at,
            _dump_redacted(turn.request.to_dict(), sort_keys=True),
            _dump_redacted(turn.intent_result.__dict__, sort_keys=True),
            _dump_redacted(turn.plan.to_dict(), sort_keys=True),
            turn.plan_hash,
            turn.policy_status,
        ],
    )


def finish_prepared_turn(
    conn,
    prepared_turn_id: str,
    *,
    status: str,
) -> None:
    conn.execute(
        """
        UPDATE prepared_assistant_turn
        SET status = ?, finished_at = ?
        WHERE prepared_turn_id = ?
        """,
        [status, _now(), prepared_turn_id],
    )
