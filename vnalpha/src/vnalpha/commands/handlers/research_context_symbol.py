from __future__ import annotations

import duckdb

from vnalpha.commands.handlers.research_context_views import (
    sector_disclosure_panels,
    sector_table,
)
from vnalpha.commands.models import CommandResult, CommandStatus, ResultPanel
from vnalpha.research_intelligence.models import SectorStrengthSnapshot
from vnalpha.warehouse.repositories import get_symbol_sector_alignment


def symbol_sector_strength(
    conn: duckdb.DuckDBPyConnection, symbol: str, requested_date: str | None
) -> CommandResult:
    alignment = get_symbol_sector_alignment(conn, symbol, requested_date)
    if alignment is None:
        return _insufficient_alignment_result(
            symbol,
            "No persisted research context data for this symbol.",
            "No persisted symbol metadata is available; no sector was inferred.",
        )
    if alignment.sector is None:
        return _insufficient_alignment_result(
            symbol,
            "Persisted research context has no sector metadata for this symbol.",
            "No sector was inferred from incomplete persisted metadata.",
        )
    if alignment.snapshot is None:
        date_context = f" for {requested_date}" if requested_date else ""
        return CommandResult(
            status=CommandStatus.EMPTY_RESULT,
            title=f"/sector-strength {symbol}",
            summary=(
                f"No persisted sector snapshot{date_context} for {alignment.sector}. "
                "This command reads persisted research data only."
            ),
            panels=[_alignment_panel(symbol, alignment.sector, "INSUFFICIENT_DATA")],
            warnings=[
                "No sector snapshot is available for the persisted source sector."
            ],
        )

    snapshot = alignment.snapshot
    return CommandResult(
        status=_snapshot_status(snapshot.quality),
        title=f"/sector-strength {symbol} — {snapshot.as_of_date.isoformat()}",
        summary="Persisted research context; no live calculation was performed.",
        tables=[sector_table([snapshot])],
        panels=[
            _alignment_panel(symbol, alignment.sector, _alignment_label(snapshot)),
            *sector_disclosure_panels([snapshot]),
        ],
        warnings=list(snapshot.caveats),
    )


def _insufficient_alignment_result(
    symbol: str, summary: str, warning: str
) -> CommandResult:
    return CommandResult(
        status=CommandStatus.EMPTY_RESULT,
        title=f"/sector-strength {symbol}",
        summary=summary,
        panels=[_alignment_panel(symbol, "—", "INSUFFICIENT_DATA")],
        warnings=[warning],
    )


def _alignment_panel(symbol: str, source_sector: str, alignment: str) -> ResultPanel:
    return ResultPanel(
        title="Sector Alignment",
        content={
            "Symbol": symbol,
            "Source sector": source_sector,
            "Alignment": alignment,
        },
    )


def _snapshot_status(quality: str) -> CommandStatus:
    return CommandStatus.SUCCESS if quality == "COMPLETE" else CommandStatus.PARTIAL


def _alignment_label(snapshot: SectorStrengthSnapshot) -> str:
    match snapshot.quality:
        case "COMPLETE":
            match snapshot.rotation:
                case "IMPROVING":
                    return "IMPROVING"
                case "WEAKENING":
                    return "WEAKENING"
                case _:
                    if snapshot.rank <= 3 and snapshot.score >= 0.75:
                        return "STRONG"
                    if snapshot.score <= 0.25:
                        return "WEAK"
                    return "NEUTRAL"
        case _:
            return "INSUFFICIENT_DATA"
