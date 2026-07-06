"""/note command handler."""

from __future__ import annotations

from vnalpha.commands.models import CommandResult, ParsedCommand
from vnalpha.commands.normalizers import normalize_symbol


def handle_note(
    parsed: ParsedCommand,
    conn=None,
    session_id: str | None = None,
    **kwargs,
) -> CommandResult:
    """Create a research note linked to a symbol."""
    if conn is None:
        return CommandResult(status="FAILED", title="/note", summary="No database connection.")

    if len(parsed.positional) < 2:
        return CommandResult(
            status="VALIDATION_ERROR",
            title="/note",
            summary='Usage: /note SYMBOL "note text"',
        )

    symbol = normalize_symbol(parsed.positional[0])
    note_text = " ".join(parsed.positional[1:])
    tags_raw = parsed.options.get("tags")
    tags = [t.strip() for t in str(tags_raw).split(",")] if tags_raw else []

    tool_executor = kwargs.get("tool_executor")
    if tool_executor is None:
        return CommandResult(status="FAILED", title=f"/note {symbol}", summary="No tool executor available.")
    output = tool_executor.call(
        "note.create",
        symbol=symbol,
        note_text=note_text,
        session_id=session_id,
        tags=tags,
    )

    return CommandResult(
        status="SUCCESS",
        title=f"/note {symbol}",
        summary=output.summary,
    )
