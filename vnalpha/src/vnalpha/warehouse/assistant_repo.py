from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_assistant_session(
    conn,
    *,
    surface: str,
    user_prompt: str,
    intent: str | None = None,
) -> str:
    session_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO assistant_session
            (assistant_session_id, started_at, status, surface, user_prompt, intent)
        VALUES (?, ?, 'RUNNING', ?, ?, ?)
        """,
        [session_id, _now(), surface, user_prompt, intent],
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
            json.dumps(plan) if plan else None,
            json.dumps(answer) if answer else None,
            refusal_reason,
            json.dumps(error) if error else None,
            session_id,
        ],
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
            model,
            _now(),
            json.dumps(input_summary) if input_summary else None,
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
            model,
            json.dumps(output_summary) if output_summary else None,
            json.dumps(usage) if usage else None,
            json.dumps(error) if error else None,
            trace_id,
        ],
    )
