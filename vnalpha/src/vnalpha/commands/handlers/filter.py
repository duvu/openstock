"""/filter command handler."""

from __future__ import annotations

from vnalpha.commands.models import (
    CommandError,
    CommandResult,
    ParsedCommand,
    ResultColumn,
    ResultTable,
)
from vnalpha.commands.normalizers import normalize_date

_SUPPORTED_FILTER_FIELDS = {
    "score",
    "candidate_class",
    "class",
    "setup_type",
    "setup",
    "rank",
    "risk_flags",
    "data_quality_status",
    "symbol",
}
_NUMERIC_FIELDS = {"score", "rank"}


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
    validation_error = _validate_filters(filter_dicts)
    if validation_error:
        return CommandResult(
            status="VALIDATION_ERROR",
            title="/filter",
            summary=validation_error,
            error=CommandError(error_type="CommandValidationError", message=validation_error),
        )

    tool_executor = kwargs.get("tool_executor")
    if tool_executor is not None:
        output = tool_executor.call("watchlist.filter", date=date, filters=filter_dicts)
    else:
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


def _validate_filters(filters: list[dict]) -> str | None:
    for item in filters:
        key = str(item.get("key", ""))
        op = str(item.get("op", ""))
        value = str(item.get("value", ""))
        if key not in _SUPPORTED_FILTER_FIELDS:
            return f"Unsupported filter field: {key}"
        if key in _NUMERIC_FIELDS and op in {">", ">=", "<", "<="}:
            try:
                float(value)
            except ValueError:
                return f"Filter {key}{op}{value} requires a numeric value."
    return None
