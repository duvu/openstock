"""Research-only /sector-strength command handler."""

from __future__ import annotations

from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ParsedCommand,
    ResultPanel,
)
from vnalpha.commands.normalizers import normalize_date, normalize_symbol


def handle_sector_strength(parsed: ParsedCommand, conn=None, **kwargs) -> CommandResult:
    if conn is None:
        return CommandResult(
            CommandStatus.FAILED, "/sector-strength", summary="No database connection."
        )
    executor = kwargs.get("tool_executor")
    if executor is None:
        return CommandResult(
            CommandStatus.FAILED,
            "/sector-strength",
            summary="No tool executor available.",
        )
    date = normalize_date(parsed.options.get("date"))
    top = int(parsed.options.get("top", 10))
    output = executor.call("sector.get_strength", date=date, top=top)
    panels = [ResultPanel(title="Sector Strength", content=output.data)]
    warnings = list(output.warnings)
    if parsed.positional:
        symbol = normalize_symbol(parsed.positional[0])
        alignment = executor.call(
            "sector.get_symbol_alignment", symbol=symbol, date=date
        )
        panels.append(ResultPanel(title="Symbol Alignment", content=alignment.data))
        warnings.extend(alignment.warnings)
    panels.append(ResultPanel(title="Caveats", content={"caveats": warnings}))
    return CommandResult(
        CommandStatus.PARTIAL if warnings else CommandStatus.SUCCESS,
        f"/sector-strength - {date}",
        summary=output.summary,
        panels=panels,
        warnings=warnings,
    )
