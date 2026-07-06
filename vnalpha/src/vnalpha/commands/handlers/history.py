"""/history command handler."""

from __future__ import annotations

from vnalpha.commands.models import (
    CommandResult,
    ParsedCommand,
    ResultColumn,
    ResultTable,
)


def handle_history(
    parsed: ParsedCommand,
    conn=None,
    **kwargs,
) -> CommandResult:
    """Show recent research sessions."""
    if conn is None:
        return CommandResult(status="FAILED", title="/history", summary="No database connection.")

    limit_raw = parsed.options.get("limit", 20)
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        limit = 20

    tool_executor = kwargs.get("tool_executor")
    if tool_executor is not None:
        output = tool_executor.call("history.list_sessions", limit=limit)
    else:
        from vnalpha.tools.notes import list_sessions
        output = list_sessions(conn, limit=limit)
    sessions = output.data or []

    if not sessions:
        return CommandResult(
            status="SUCCESS",
            title="/history",
            summary="No research sessions recorded yet.",
        )

    rows = [
        [
            s.get("started_at", "")[:19] if s.get("started_at") else "",
            s.get("command_text", ""),
            s.get("status", ""),
            s.get("surface", ""),
        ]
        for s in sessions
    ]
    table = ResultTable(
        title=f"Recent Sessions (last {len(sessions)})",
        columns=[
            ResultColumn("started_at", "Started"),
            ResultColumn("command", "Command"),
            ResultColumn("status", "Status"),
            ResultColumn("surface", "Surface"),
        ],
        rows=rows,
    )
    return CommandResult(
        status="SUCCESS",
        title="/history",
        summary=output.summary,
        tables=[table],
    )
