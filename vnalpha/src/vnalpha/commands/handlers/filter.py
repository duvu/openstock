"""/filter command handler."""

from __future__ import annotations

from vnalpha.commands.models import (
    CommandResult,
    ParsedCommand,
    ResultColumn,
    ResultTable,
)
from vnalpha.commands.normalizers import normalize_date


def handle_filter(
    parsed: ParsedCommand,
    conn=None,
    **kwargs,
) -> CommandResult:
    """Filter candidate scores by deterministic conditions."""
    if conn is None:
        return CommandResult(status="FAILED", title="/filter", summary="No database connection.")

    date = normalize_date(parsed.options.get("date"))

    # Build filter dicts from ParsedCommand.filters
    filter_dicts = [
        {"key": f.key, "op": f.op, "value": f.value}
        for f in parsed.filters
    ]

    from vnalpha.tools.watchlist import filter_watchlist

    output = filter_watchlist(conn, date=date, filters=filter_dicts)
    rows_data = output.data or []

    if not rows_data:
        return CommandResult(
            status="SUCCESS",
            title=f"/filter — {date}",
            summary=f"No candidates matched the filter on {date}.",
        )

    rows = [
        [
            r.get("symbol", ""),
            f"{r.get('score', 0):.3f}" if r.get("score") is not None else "—",
            r.get("candidate_class", ""),
            r.get("setup_type", ""),
        ]
        for r in rows_data
    ]
    table = ResultTable(
        title=f"Filtered Candidates {date}",
        columns=[
            ResultColumn("symbol", "Symbol"),
            ResultColumn("score", "Score"),
            ResultColumn("class", "Class"),
            ResultColumn("setup", "Setup"),
        ],
        rows=rows,
    )
    return CommandResult(
        status="SUCCESS",
        title=f"/filter — {date}",
        summary=output.summary,
        tables=[table],
    )
