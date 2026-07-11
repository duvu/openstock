"""Research-only /analyze command handler."""

from __future__ import annotations

from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ParsedCommand,
    ResultPanel,
)
from vnalpha.commands.normalizers import normalize_date, normalize_symbol


def handle_analyze(parsed: ParsedCommand, conn=None, **kwargs) -> CommandResult:
    """Render deterministic deep-analysis blocks from the local analysis tool."""
    if conn is None:
        return CommandResult(
            CommandStatus.FAILED, "/analyze", summary="No database connection."
        )
    if not parsed.positional:
        return CommandResult(
            CommandStatus.VALIDATION_ERROR,
            "/analyze",
            summary="Usage: /analyze SYMBOL [--date DATE] [--with-sector] [--with-regime]",
        )
    tool_executor = kwargs.get("tool_executor")
    if tool_executor is None:
        return CommandResult(
            CommandStatus.FAILED, "/analyze", summary="No tool executor available."
        )
    symbol = normalize_symbol(parsed.positional[0])
    date = normalize_date(parsed.options.get("date"))
    output = tool_executor.call(
        "analysis.deep_symbol",
        symbol=symbol,
        date=date,
        with_sector=bool(parsed.options.get("with-sector", False)),
        with_regime=bool(parsed.options.get("with-regime", False)),
    )
    analysis = output.data
    return CommandResult(
        CommandStatus.PARTIAL if output.warnings else CommandStatus.SUCCESS,
        f"/analyze {symbol} - {date}",
        summary=output.summary,
        panels=[
            ResultPanel(title="Trend", content=analysis["trend"]),
            ResultPanel(title="Levels", content=analysis["levels"]),
            ResultPanel(title="Setup Quality", content=analysis["setup_quality"]),
            ResultPanel(title="Scenario", content=analysis["scenario"]),
            ResultPanel(
                title="Caveats",
                content={
                    "risks": analysis["risk_caveats"],
                    "missing_data": analysis["missing_data"],
                },
            ),
        ],
        warnings=output.warnings,
    )
