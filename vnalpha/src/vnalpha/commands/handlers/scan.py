"""/scan command handler."""

from __future__ import annotations

from vnalpha.commands.models import (
    CommandError,
    CommandResult,
    ParsedCommand,
    ResultColumn,
    ResultTable,
)
from vnalpha.commands.normalizers import normalize_date


def handle_scan(
    parsed: ParsedCommand,
    conn=None,
    **kwargs,
) -> CommandResult:
    """Scan the daily watchlist for a date."""
    if conn is None:
        return CommandResult(status="FAILED", title="/scan", summary="No database connection.")

    date = normalize_date(parsed.options.get("date"))
    universe_hint = parsed.positional[0].upper() if parsed.positional else None
    universe_symbols = None
    if universe_hint:
        try:
            from vnalpha.core.universe import resolve_universe
            universe_symbols = set(resolve_universe(universe_hint))
        except ValueError as exc:
            return CommandResult(
                status="VALIDATION_ERROR",
                title="/scan",
                summary=str(exc),
                error=CommandError(error_type="CommandValidationError", message=str(exc)),
            )

    tool_executor = kwargs.get("tool_executor")
    if tool_executor is None:
        return CommandResult(status="FAILED", title="/scan", summary="No tool executor available.")
    output = tool_executor.call("watchlist.scan", date=date)
    rows_data = output.data or []
    if universe_symbols is not None:
        rows_data = [r for r in rows_data if r.get("symbol") in universe_symbols]

    if not rows_data:
        return CommandResult(
            status="SUCCESS",
            title=f"/scan — {date}",
            summary=f"No candidates on {date}. Run 'vnalpha score --date {date}' first.",
            warnings=["Watchlist is empty."],
        )

    rows = [
        [
            r.get("rank", ""),
            r.get("symbol", ""),
            f"{r.get('score', 0):.3f}" if r.get("score") is not None else "—",
            r.get("candidate_class", ""),
            r.get("setup_type", ""),
            _format_risk_flags(r.get("risk_flags_json")),
            r.get("data_quality_status", "unknown"),
        ]
        for r in rows_data
    ]
    table = ResultTable(
        title=f"Watchlist {date}" + (f" [{universe_hint}]" if universe_hint else ""),
        columns=[
            ResultColumn("rank", "Rank"),
            ResultColumn("symbol", "Symbol"),
            ResultColumn("score", "Score"),
            ResultColumn("class", "Class"),
            ResultColumn("setup", "Setup"),
            ResultColumn("risk_flags", "Risk Flags"),
            ResultColumn("quality", "Quality"),
        ],
        rows=rows,
    )
    return CommandResult(
        status="SUCCESS",
        title=f"/scan — {date}",
        summary=output.summary,
        tables=[table],
    )


def _format_risk_flags(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) or "—"
    return str(value) if value else "—"
