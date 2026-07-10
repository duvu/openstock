"""/compare command handler."""

from __future__ import annotations

from typing import assert_never

from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ParsedCommand,
    ResultColumn,
    ResultTable,
)
from vnalpha.commands.normalizers import normalize_date, normalize_symbols
from vnalpha.core.logging import get_logger
from vnalpha.data_availability.models import EnsureDataStatus

logger = get_logger("commands.compare")


def handle_compare(
    parsed: ParsedCommand,
    conn=None,
    **kwargs,
) -> CommandResult:
    """Compare a list of symbols using their persisted candidate scores."""
    if conn is None:
        return CommandResult(
            status=CommandStatus.FAILED,
            title="/compare",
            summary="No database connection.",
        )

    if not parsed.positional:
        return CommandResult(
            status=CommandStatus.VALIDATION_ERROR,
            title="/compare",
            summary="Usage: /compare SYMBOL1 SYMBOL2 [SYMBOL3...]",
        )

    symbols = normalize_symbols(parsed.positional)
    date = normalize_date(parsed.options.get("date"))

    ensure_warnings: list[str] = []
    provisioning_degraded = False
    try:
        from vnalpha.data_availability import ensure_symbol_analysis_ready

        for sym in symbols:
            try:
                ensure_result = ensure_symbol_analysis_ready(conn, sym, date)
                ensure_warnings.extend(ensure_result.warnings)
                match ensure_result.status:
                    case EnsureDataStatus.READY:
                        pass
                    case EnsureDataStatus.PARTIAL | EnsureDataStatus.FAILED:
                        provisioning_degraded = True
                    case unreachable:
                        assert_never(unreachable)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Data provisioning failed for %s: %s", sym, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Data provisioning import failed: %s", exc)

    tool_executor = kwargs.get("tool_executor")
    if tool_executor is None:
        return CommandResult(
            status=CommandStatus.FAILED,
            title="/compare",
            summary="No tool executor available.",
        )
    output = tool_executor.call("candidate.compare", symbols=symbols, date=date)
    records = output.data or []

    if not records:
        return CommandResult(
            status=CommandStatus.EMPTY_RESULT,
            title=f"/compare — {date}",
            summary=f"No scores found for {symbols} on {date}.",
            warnings=list(output.warnings) + ensure_warnings,
        )

    rows = [
        [
            r.get("symbol", ""),
            f"{r.get('score', 0):.3f}" if r.get("score") is not None else "—",
            r.get("candidate_class", ""),
            r.get("setup_type", ""),
            f"{r.get('trend_score', 0):.2f}"
            if r.get("trend_score") is not None
            else "—",
            f"{r.get('relative_strength_score', 0):.2f}"
            if r.get("relative_strength_score") is not None
            else "—",
            f"{r.get('volume_score', 0):.2f}"
            if r.get("volume_score") is not None
            else "—",
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
    all_warnings = list(output.warnings) + ensure_warnings
    return CommandResult(
        status=(
            CommandStatus.PARTIAL if provisioning_degraded else CommandStatus.SUCCESS
        ),
        title=f"/compare — {date}",
        summary=output.summary,
        tables=[table],
        warnings=all_warnings,
    )


def _format_risk_flags(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) or "—"
    return str(value) if value else "—"
