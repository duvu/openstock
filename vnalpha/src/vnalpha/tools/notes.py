"""note.create and history.list_sessions tools (stubs — use warehouse repos)."""

from __future__ import annotations

import duckdb

from vnalpha.tools.models import ToolOutput


def create_note(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    note_text: str,
    session_id: str | None = None,
    tags: list[str] | None = None,
) -> ToolOutput:
    """Create a research note linked to a symbol."""
    from vnalpha.warehouse.session_repo import create_research_note

    note_id = create_research_note(
        conn, symbol=symbol, note_text=note_text, session_id=session_id, tags=tags
    )
    return ToolOutput(
        data={"note_id": note_id, "symbol": symbol, "note_text": note_text},
        summary=f"Note saved for {symbol} (id={note_id[:8]}...).",
    )


def list_sessions(
    conn: duckdb.DuckDBPyConnection,
    limit: int = 20,
) -> ToolOutput:
    """Return recent research sessions."""
    from vnalpha.warehouse.session_repo import list_research_sessions

    sessions = list_research_sessions(conn, limit=limit)
    return ToolOutput(
        data=sessions,
        summary=f"{len(sessions)} recent sessions.",
    )
