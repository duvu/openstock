"""/explain command handler."""

from __future__ import annotations

from vnalpha.commands.models import (
    CommandResult,
    ParsedCommand,
    ResultPanel,
)
from vnalpha.commands.normalizers import normalize_date, normalize_symbol
from vnalpha.core.logging import get_logger

logger = get_logger("commands.explain")


def handle_explain(
    parsed: ParsedCommand,
    conn=None,
    **kwargs,
) -> CommandResult:
    """Explain a symbol from persisted candidate score artifacts.

    Automatically provisions missing data (OHLCV, canonical, features, score)
    before running the analysis.
    """
    if conn is None:
        return CommandResult(
            status="FAILED", title="/explain", summary="No database connection."
        )

    if not parsed.positional:
        return CommandResult(
            status="VALIDATION_ERROR",
            title="/explain",
            summary="Usage: /explain SYMBOL [--date DATE]",
        )

    symbol = normalize_symbol(parsed.positional[0])
    date = normalize_date(parsed.options.get("date"))

    ensure_result = None
    try:
        from vnalpha.data_availability import ensure_symbol_analysis_ready

        ensure_result = ensure_symbol_analysis_ready(conn, symbol, date)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Data provisioning failed for %s: %s", symbol, exc)

    tool_executor = kwargs.get("tool_executor")
    if tool_executor is None:
        return CommandResult(
            status="FAILED",
            title=f"/explain {symbol}",
            summary="No tool executor available.",
        )
    output = tool_executor.call("candidate.explain", symbol=symbol, date=date)
    quality_output = tool_executor.call("quality.get_status", symbol=symbol, date=date)

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
        ResultPanel(title="Data Quality", content={"rows": quality_output.data or []}),
        ResultPanel(title="Lineage", content=lineage),
    ]
    if ensure_result is not None:
        panels.append(
            ResultPanel(title="Data Readiness", content=ensure_result.to_panel_dict())
        )

    all_warnings = list(output.warnings)
    if ensure_result is not None:
        all_warnings.extend(ensure_result.warnings)

    return CommandResult(
        status="SUCCESS",
        title=f"/explain {symbol} — {date}",
        summary=output.summary,
        panels=panels,
        warnings=all_warnings,
    )
