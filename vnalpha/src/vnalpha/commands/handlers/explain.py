"""/explain command handler."""

from __future__ import annotations

from vnalpha.commands.models import (
    CommandResult,
    ParsedCommand,
    ResultPanel,
)
from vnalpha.commands.normalizers import normalize_date, normalize_symbol


def handle_explain(
    parsed: ParsedCommand,
    conn=None,
    **kwargs,
) -> CommandResult:
    """Explain a symbol from persisted candidate score artifacts."""
    if conn is None:
        return CommandResult(status="FAILED", title="/explain", summary="No database connection.")

    if not parsed.positional:
        return CommandResult(
            status="VALIDATION_ERROR",
            title="/explain",
            summary="Usage: /explain SYMBOL [--date DATE]",
        )

    symbol = normalize_symbol(parsed.positional[0])
    date = normalize_date(parsed.options.get("date"))

    from vnalpha.tools.scoring import explain_candidate

    output = explain_candidate(conn, symbol=symbol, date=date)

    if output.data is None:
        return CommandResult(
            status="SUCCESS",
            title=f"/explain {symbol} — {date}",
            summary=output.summary,
            warnings=output.warnings,
        )

    rec = output.data
    score_info = {
        "symbol": rec.get("symbol"),
        "date": rec.get("date"),
        "score": rec.get("score"),
        "candidate_class": rec.get("candidate_class"),
        "setup_type": rec.get("setup_type"),
    }
    evidence = rec.get("evidence_json") or {}
    risk_flags = rec.get("risk_flags_json") or []
    lineage = rec.get("lineage_json") or {}

    panels = [
        ResultPanel(title="Score Summary", content=score_info),
        ResultPanel(title="Score Breakdown", content=evidence),
        ResultPanel(title="Risk Flags", content={"flags": risk_flags}),
        ResultPanel(title="Lineage", content=lineage),
    ]
    return CommandResult(
        status="SUCCESS",
        title=f"/explain {symbol} — {date}",
        summary=output.summary,
        panels=panels,
        warnings=output.warnings,
    )
