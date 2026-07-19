"""Repository helpers for Phase 5.8 command-layer tables.

Tables: research_session, tool_trace, research_note
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.core.text_safety import redact_structure, sanitize_text

logger = get_logger("warehouse.session_repo")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _dump_redacted(value: object) -> str:
    return json.dumps(redact_structure(value, parse_json_strings=True))


# ---------------------------------------------------------------------------
# research_session
# ---------------------------------------------------------------------------


def create_research_session(
    conn: duckdb.DuckDBPyConnection,
    surface: str,
    command_text: str,
    command_name: Optional[str] = None,
    parsed_args: Optional[dict[str, Any]] = None,
) -> str:
    """Insert a new research_session row with status RUNNING. Returns session_id."""
    session_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO research_session
        (session_id, started_at, status, surface, command_text, command_name, parsed_args_json)
        VALUES (?, ?, 'RUNNING', ?, ?, ?, ?)
        """,
        [
            session_id,
            _now_utc(),
            sanitize_text(surface),
            sanitize_text(command_text),
            sanitize_text(command_name) if command_name else None,
            _dump_redacted(parsed_args or {}),
        ],
    )
    return session_id


def finish_research_session(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
    status: str = "SUCCESS",
    result_summary: Optional[dict[str, Any]] = None,
    error: Optional[dict[str, Any]] = None,
) -> None:
    """Mark a research_session as finished."""
    conn.execute(
        """
        UPDATE research_session
        SET finished_at = ?, status = ?, result_summary_json = ?, error_json = ?
        WHERE session_id = ?
        """,
        [
            _now_utc(),
            status,
            _dump_redacted(result_summary) if result_summary else None,
            _dump_redacted(error) if error else None,
            session_id,
        ],
    )


def update_research_session_parse(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
    command_name: Optional[str],
    parsed_args: Optional[dict[str, Any]] = None,
) -> None:
    """Store parsed command details after a session was created."""
    conn.execute(
        """
        UPDATE research_session
        SET command_name = ?, parsed_args_json = ?
        WHERE session_id = ?
        """,
        [
            sanitize_text(command_name) if command_name else None,
            _dump_redacted(parsed_args or {}),
            session_id,
        ],
    )


def list_research_sessions(
    conn: duckdb.DuckDBPyConnection,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return recent research sessions ordered by started_at descending."""
    rows = conn.execute(
        """
        SELECT session_id, started_at, finished_at, status,
               surface, command_text, command_name
        FROM research_session
        ORDER BY started_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    cols = [
        "session_id",
        "started_at",
        "finished_at",
        "status",
        "surface",
        "command_text",
        "command_name",
    ]
    return [
        {k: str(v) if v is not None else None for k, v in zip(cols, row, strict=True)}
        for row in rows
    ]


# ---------------------------------------------------------------------------
# tool_trace
# ---------------------------------------------------------------------------


def create_tool_trace(
    conn: duckdb.DuckDBPyConnection,
    session_id: Optional[str],
    tool_name: str,
    input_data: Optional[dict[str, Any]] = None,
    *,
    assistant_session_id: Optional[str] = None,
    trace_parent_type: Optional[str] = None,
) -> str:
    """Insert a new tool_trace row with status RUNNING. Returns tool_trace_id."""
    trace_id = str(uuid.uuid4())
    if trace_parent_type is None:
        trace_parent_type = "assistant" if assistant_session_id else "command"
    conn.execute(
        """
        INSERT INTO tool_trace
        (tool_trace_id, session_id, assistant_session_id, trace_parent_type,
         tool_name, started_at, status, input_json)
        VALUES (?, ?, ?, ?, ?, ?, 'RUNNING', ?)
        """,
        [
            trace_id,
            session_id,
            assistant_session_id,
            trace_parent_type,
            sanitize_text(tool_name),
            _now_utc(),
            _dump_redacted(input_data or {}),
        ],
    )
    return trace_id


def finish_tool_trace(
    conn: duckdb.DuckDBPyConnection,
    trace_id: str,
    status: str = "SUCCESS",
    output_summary: Optional[dict[str, Any]] = None,
    error: Optional[dict[str, Any]] = None,
) -> None:
    """Mark a tool_trace as finished."""
    conn.execute(
        """
        UPDATE tool_trace
        SET finished_at = ?, status = ?, output_summary_json = ?, error_json = ?
        WHERE tool_trace_id = ?
        """,
        [
            _now_utc(),
            status,
            _dump_redacted(output_summary) if output_summary else None,
            _dump_redacted(error) if error else None,
            trace_id,
        ],
    )


# ---------------------------------------------------------------------------
# research_note
# ---------------------------------------------------------------------------


def create_research_note(
    conn: duckdb.DuckDBPyConnection,
    note_text: str,
    symbol: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> str:
    """Insert a new research_note. Returns note_id."""
    note_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO research_note
        (note_id, created_at, symbol, session_id, note_text, tags_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            note_id,
            _now_utc(),
            sanitize_text(symbol) if symbol else None,
            session_id,
            sanitize_text(note_text),
            _dump_redacted(tags or []),
        ],
    )
    return note_id


def list_research_notes(
    conn: duckdb.DuckDBPyConnection,
    symbol: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return recent notes, optionally filtered by symbol."""
    if symbol:
        rows = conn.execute(
            """
            SELECT note_id, created_at, symbol, note_text, tags_json
            FROM research_note WHERE symbol = ?
            ORDER BY created_at DESC LIMIT ?
            """,
            [symbol, limit],
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT note_id, created_at, symbol, note_text, tags_json
            FROM research_note ORDER BY created_at DESC LIMIT ?
            """,
            [limit],
        ).fetchall()
    cols = ["note_id", "created_at", "symbol", "note_text", "tags_json"]
    result = []
    for row in rows:
        rec = dict(zip(cols, row, strict=True))
        if isinstance(rec["tags_json"], str):
            rec["tags_json"] = json.loads(rec["tags_json"])
        if rec["created_at"] is not None:
            rec["created_at"] = str(rec["created_at"])
        result.append(rec)
    return result
