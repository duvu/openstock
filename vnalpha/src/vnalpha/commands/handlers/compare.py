"""/compare command handler."""

from __future__ import annotations

from vnalpha.commands.models import (
    CommandResult,
    ParsedCommand,
    ResultColumn,
    ResultTable,
)
from vnalpha.commands.normalizers import normalize_date, normalize_symbols


def handle_compare(
    parsed: ParsedCommand,
    conn=None,
    **kwargs,
) -> CommandResult:
    """Compare a list of symbols using their persisted candidate scores."""
    if conn is None:
        return CommandResult(status="FAILED", title="/compare", summary="No database connection.")

    if not parsed.positional:
        return CommandResult(
            status="VALIDATION_ERROR",
            title="/compare",
            summary="Usage: /compare SYMBOL1 SYMBOL2 [SYMBOL3...]",
        )

    symbols = normalize_symbols(parsed.positional)
    date = normalize_date(parsed.options.get("date"))

    tool_executor = kwargs.get("tool_executor")
    if tool_executor is None:
        return CommandResult(status="FAILED", title="/compare", summary="No tool executor available.")
    output = tool_executor.call("candidate.compare", symbols=symbols, date=date)
    records = output.data or []

    if not records:
        return CommandResult(
            status="SUCCESS",
            title=f"/compare — {date}",
            summary=f"No scores found for {symbols} on {date}.",
            warnings=output.warnings,
        )

    rows = [
        [
            r.get("symbol", ""),
            f"{r.get('score', 0):.3f}" if r.get("score") is not None else "—",
            r.get("candidate_class", ""),
            r.get("setup_type", ""),
            f"{r.get('trend_score', 0):.2f}" if r.get("trend_score") is not None else "—",
            f"{r.get('relative_strength_score', 0):.2f}" if r.get("relative_strength_score") is not None else "—",
            f"{r.get('volume_score', 0):.2f}" if r.get("volume_score") is not None else "—",
            _format_risk_flags(r.get("risk_flags_json")),
            r.get("data_quality_status", "unknown"),
        ]
        for r in records
    ]
    table = ResultTable(
        title=f"Comparison {date}",
        columns=[
            ResultColumn("symbol", "Symbol"),
            ResultColumn("score", "Score"),
            ResultColumn("class", "Class"),
            ResultColumn("setup", "Setup"),
            ResultColumn("trend", "Trend"),
            ResultColumn("rs", "RS"),
            ResultColumn("volume", "Volume"),
            ResultColumn("risk_flags", "Risk Flags"),
            ResultColumn("quality", "Quality"),
        ],
        rows=rows,
    )
    return CommandResult(
        status="SUCCESS",
        title=f"/compare — {date}",
        summary=output.summary,
        tables=[table],
        warnings=output.warnings,
    )


def _format_risk_flags(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) or "—"
    return str(value) if value else "—"
