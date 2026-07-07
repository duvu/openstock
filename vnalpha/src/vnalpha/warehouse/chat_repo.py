"""Repository helpers for Phase 5.10 chat persistence tables.

Tables: chat_session, chat_message
"""

from __future__ import annotations

import json as _json
import uuid
from datetime import datetime, timezone
from typing import Optional

import duckdb

from vnalpha.core.logging import get_logger

logger = get_logger("warehouse.chat_repo")


def _now_utc_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# chat_session
# ---------------------------------------------------------------------------


def create_chat_session(
    conn: duckdb.DuckDBPyConnection,
    *,
    surface: str = "tui-chat",
    target_date: Optional[str] = None,
    title: Optional[str] = None,
) -> str:
    """Insert a new chat_session row with status 'active'. Returns chat_session_id."""
    chat_session_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO chat_session
        (chat_session_id, started_at, status, surface, target_date, title)
        VALUES (?, ?, 'active', ?, ?, ?)
        """,
        [
            chat_session_id,
            _now_utc_iso(),
            surface,
            target_date,
            title,
        ],
    )
    return chat_session_id


def finish_chat_session(
    conn: duckdb.DuckDBPyConnection,
    chat_session_id: str,
) -> None:
    """Mark a chat_session as 'finished' and set updated_at."""
    conn.execute(
        """
        UPDATE chat_session
        SET status = 'finished', updated_at = ?
        WHERE chat_session_id = ?
        """,
        [_now_utc_iso(), chat_session_id],
    )


def update_chat_session_context(
    conn: duckdb.DuckDBPyConnection,
    chat_session_id: str,
    context_json: str,
) -> None:
    """Store serialised context JSON on a chat_session and refresh updated_at."""
    conn.execute(
        """
        UPDATE chat_session
        SET context_json = ?, updated_at = ?
        WHERE chat_session_id = ?
        """,
        [context_json, _now_utc_iso(), chat_session_id],
    )


# ---------------------------------------------------------------------------
# chat_message
# ---------------------------------------------------------------------------


def append_chat_message(
    conn: duckdb.DuckDBPyConnection,
    *,
    chat_session_id: str,
    role: str,
    content: str,
    message_type: str = "plain_text",
    assistant_session_id: Optional[str] = None,
    research_session_id: Optional[str] = None,
    tool_trace_ids_json: Optional[str] = None,
    plan_json: Optional[str] = None,
    metadata_json: Optional[str] = None,
) -> str:
    """Insert a chat_message and return its chat_message_id."""
    chat_message_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO chat_message
        (chat_message_id, chat_session_id, created_at, role, content,
         message_type, assistant_session_id, research_session_id,
         tool_trace_ids_json, plan_json, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            chat_message_id,
            chat_session_id,
            _now_utc_iso(),
            role,
            content,
            message_type,
            assistant_session_id,
            research_session_id,
            tool_trace_ids_json,
            plan_json,
            metadata_json,
        ],
    )
    return chat_message_id


def list_chat_messages(
    conn: duckdb.DuckDBPyConnection,
    chat_session_id: str,
    *,
    include_hidden: bool = False,
) -> list[dict]:
    """Return messages for a session ordered by created_at ASC.

    By default only visible messages are returned (is_visible IS NULL OR is_visible = true).
    Pass include_hidden=True to return all messages including soft-deleted ones.
    """
    visibility_clause = (
        "" if include_hidden else "AND (is_visible IS NULL OR is_visible = true)"
    )
    rows = conn.execute(
        f"""
        SELECT
            chat_message_id, chat_session_id, created_at, role, content,
            message_type, assistant_session_id, research_session_id,
            tool_trace_ids_json, plan_json, metadata_json
        FROM chat_message
        WHERE chat_session_id = ?
          AND role != 'trace'
        {visibility_clause}
        ORDER BY created_at ASC
        """,
        [chat_session_id],
    ).fetchall()
    cols = [
        "chat_message_id",
        "chat_session_id",
        "created_at",
        "role",
        "content",
        "message_type",
        "assistant_session_id",
        "research_session_id",
        "tool_trace_ids_json",
        "plan_json",
        "metadata_json",
    ]
    return [
        {k: str(v) if v is not None else None for k, v in zip(cols, row, strict=True)}
        for row in rows
    ]


def clear_visible_messages(
    conn: duckdb.DuckDBPyConnection,
    chat_session_id: str,
    *,
    forget: bool = False,
) -> int:
    """Hide or delete visible messages for a session.

    When *forget* is False (default), sets ``is_visible=false`` and records
    ``hidden_at`` on all currently visible rows — audit transcript is preserved.
    When *forget* is True, permanently deletes all messages for the session.

    Returns the count of affected rows.
    """
    row = conn.execute(
        "SELECT COUNT(*) FROM chat_message WHERE chat_session_id = ? AND (is_visible IS NULL OR is_visible = true)",
        [chat_session_id],
    ).fetchone()
    count = row[0] if row else 0
    if forget:
        conn.execute(
            "DELETE FROM chat_message WHERE chat_session_id = ?",
            [chat_session_id],
        )
    else:
        now = _now_utc_iso()
        conn.execute(
            """
            UPDATE chat_message
            SET is_visible = false, hidden_at = ?
            WHERE chat_session_id = ? AND (is_visible IS NULL OR is_visible = true)
            """,
            [now, chat_session_id],
        )
    return count


# ---------------------------------------------------------------------------
# Trace timeline helpers (Section 8 — Phase 5.10)
# ---------------------------------------------------------------------------


def append_trace_event(
    conn: duckdb.DuckDBPyConnection,
    *,
    chat_session_id: str,
    tool_name: str,
    status: str,
    elapsed_ms: float | None = None,
    tool_trace_id: str | None = None,
) -> str:
    """Insert a chat_message row representing a tool-trace lifecycle event.

    Parameters
    ----------
    status:
        One of ``"RUNNING"``, ``"SUCCESS"``, ``"FAILED"``.
    elapsed_ms:
        Duration in milliseconds; ``None`` while the tool is still running.
    tool_trace_id:
        Optional canonical tool_trace_id for back-linking.

    Returns
    -------
    str
        The new ``chat_message_id``.
    """
    if status == "RUNNING":
        content = f"\u27f3 {tool_name} running..."
    elif status == "SUCCESS":
        content = f"\u2713 {tool_name} success {int(elapsed_ms)}ms"
    elif status == "FAILED":
        content = f"\u2717 {tool_name} failed {int(elapsed_ms)}ms"
    else:
        content = f"[{status}] {tool_name}"

    tool_trace_ids_json: Optional[str] = (
        _json.dumps([tool_trace_id]) if tool_trace_id else None
    )

    return append_chat_message(
        conn,
        chat_session_id=chat_session_id,
        role="trace",
        content=content,
        message_type="tool_trace_event",
        tool_trace_ids_json=tool_trace_ids_json,
    )


def list_trace_events_for_session(
    conn: duckdb.DuckDBPyConnection,
    chat_session_id: str,
) -> list[dict]:
    """Return all tool-trace chat_message rows for *chat_session_id*, oldest first.

    Each dict contains all columns of ``chat_message``.
    """
    rows = conn.execute(
        """
        SELECT chat_message_id, chat_session_id, created_at, role, content,
               message_type, assistant_session_id, research_session_id,
               tool_trace_ids_json, plan_json, metadata_json
        FROM chat_message
        WHERE chat_session_id = ?
          AND message_type = 'tool_trace_event'
        ORDER BY created_at ASC
        """,
        [chat_session_id],
    ).fetchall()

    columns = [
        "chat_message_id",
        "chat_session_id",
        "created_at",
        "role",
        "content",
        "message_type",
        "assistant_session_id",
        "research_session_id",
        "tool_trace_ids_json",
        "plan_json",
        "metadata_json",
    ]
    return [dict(zip(columns, row, strict=False)) for row in rows]
