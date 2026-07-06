"""/quality command handler."""

from __future__ import annotations

from vnalpha.commands.models import (
    CommandResult,
    ParsedCommand,
    ResultColumn,
    ResultTable,
)
from vnalpha.commands.normalizers import normalize_date, normalize_symbol


def handle_quality(
    parsed: ParsedCommand,
    conn=None,
    **kwargs,
) -> CommandResult:
    """Show data quality for a symbol or the latest watchlist."""
    if conn is None:
        return CommandResult(status="FAILED", title="/quality", summary="No database connection.")

    symbol = normalize_symbol(parsed.positional[0]) if parsed.positional else None
    date = normalize_date(parsed.options.get("date")) if parsed.options.get("date") else None

    from vnalpha.tools.quality import get_quality_status

    output = get_quality_status(conn, symbol=symbol, date=date)

    if output.data is None:
        return CommandResult(
            status="SUCCESS",
            title=f"/quality{' ' + symbol if symbol else ''}",
            summary=output.summary,
            warnings=output.warnings,
        )

    rows_data = output.data
    if symbol:
        # Per-symbol: time series
        rows = [
            [r.get("time", ""), r.get("quality_status", ""), r.get("provider", "")]
            for r in rows_data
        ]
        table = ResultTable(
            title=f"Data Quality — {symbol}",
            columns=[
                ResultColumn("time", "Time"),
                ResultColumn("quality", "Quality"),
                ResultColumn("provider", "Provider"),
            ],
            rows=rows,
        )
    else:
        # Watchlist-level
        rows = [
            [r.get("symbol", ""), r.get("quality_status", ""), r.get("provider", "")]
            for r in rows_data
        ]
        table = ResultTable(
            title="Watchlist Data Quality",
            columns=[
                ResultColumn("symbol", "Symbol"),
                ResultColumn("quality", "Quality"),
                ResultColumn("provider", "Provider"),
            ],
            rows=rows,
        )

    return CommandResult(
        status="SUCCESS",
        title=f"/quality{' ' + symbol if symbol else ''}",
        summary=output.summary,
        tables=[table],
    )
