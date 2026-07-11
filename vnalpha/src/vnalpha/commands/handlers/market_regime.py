"""Research-only /market-regime command handler."""

from __future__ import annotations

from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ParsedCommand,
    ResultPanel,
)
from vnalpha.commands.normalizers import normalize_date


def handle_market_regime(parsed: ParsedCommand, conn=None, **kwargs) -> CommandResult:
    if conn is None:
        return CommandResult(
            CommandStatus.FAILED, "/market-regime", summary="No database connection."
        )
    executor = kwargs.get("tool_executor")
    if executor is None:
        return CommandResult(
            CommandStatus.FAILED,
            "/market-regime",
            summary="No tool executor available.",
        )
    date = normalize_date(parsed.options.get("date"))
    output = executor.call("market.get_regime", date=date)
    return CommandResult(
        CommandStatus.PARTIAL if output.warnings else CommandStatus.SUCCESS,
        f"/market-regime - {date}",
        summary=output.summary,
        panels=[
            ResultPanel(title="Market Regime", content=output.data),
            ResultPanel(title="Caveats", content={"caveats": output.warnings}),
        ],
        warnings=output.warnings,
    )
