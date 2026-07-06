"""/scan command handler."""

from __future__ import annotations

from vnalpha.commands.models import (
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
    # Optional positional: universe name (informational only — we scan watchlist)
    universe_hint = parsed.positional[0].upper() if parsed.positional else None

    from vnalpha.tools.watchlist import scan_watchlist

    output = scan_watchlist(conn, date=date)
    rows_data = output.data or []

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
