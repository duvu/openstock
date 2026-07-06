"""/lineage command handler."""

from __future__ import annotations

from vnalpha.commands.models import (
    CommandResult,
    ParsedCommand,
    ResultPanel,
)
from vnalpha.commands.normalizers import normalize_date, normalize_symbol


def handle_lineage(
    parsed: ParsedCommand,
    conn=None,
    **kwargs,
) -> CommandResult:
    """Show provider, ingestion run, feature date, and scoring version for a symbol."""
    if conn is None:
        return CommandResult(status="FAILED", title="/lineage", summary="No database connection.")

    if not parsed.positional:
        return CommandResult(
            status="VALIDATION_ERROR",
            title="/lineage",
            summary="Usage: /lineage SYMBOL [--date DATE]",
        )

    symbol = normalize_symbol(parsed.positional[0])
    date = normalize_date(parsed.options.get("date"))

    tool_executor = kwargs.get("tool_executor")
    if tool_executor is None:
        return CommandResult(status="FAILED", title=f"/lineage {symbol}", summary="No tool executor available.")
    output = tool_executor.call("lineage.get_symbol_lineage", symbol=symbol, date=date)

    if output.data is None:
        return CommandResult(
            status="SUCCESS",
            title=f"/lineage {symbol} — {date}",
            summary=output.summary,
            warnings=output.warnings,
        )

    return CommandResult(
        status="SUCCESS",
        title=f"/lineage {symbol} — {date}",
        summary=output.summary,
        panels=[ResultPanel(title="Lineage", content=output.data)],
    )
