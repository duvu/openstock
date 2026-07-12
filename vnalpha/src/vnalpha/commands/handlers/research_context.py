from __future__ import annotations

import duckdb

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.handlers.research_context_symbol import symbol_sector_strength
from vnalpha.commands.handlers.research_context_validation import validate_command_input
from vnalpha.commands.handlers.research_context_views import (
    caveat_panel,
    percentage,
    sector_disclosure_panels,
    sector_table,
    snapshot_warnings,
)
from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ParsedCommand,
    ResultArtifact,
    ResultPanel,
)
from vnalpha.commands.normalizers import normalize_date, normalize_symbol
from vnalpha.research_intelligence.models import SectorStrengthSnapshot
from vnalpha.warehouse.repositories import (
    get_latest_market_regime,
    get_latest_sector_strength,
    get_market_regime_as_of,
    get_sector_strength_as_of,
)


def handle_market_regime(parsed: ParsedCommand, conn=None, **kwargs) -> CommandResult:
    if conn is None:
        return CommandResult(
            status=CommandStatus.FAILED,
            title="/market-regime",
            summary="No database connection.",
        )

    validate_command_input(parsed, {"date"}, maximum_positionals=0)
    requested_date = _requested_date(parsed)
    snapshot = (
        get_latest_market_regime(conn)
        if requested_date is None
        else get_market_regime_as_of(conn, requested_date)
    )
    if snapshot is None:
        date_context = f" for {requested_date}" if requested_date else ""
        return CommandResult(
            status=CommandStatus.EMPTY_RESULT,
            title="/market-regime",
            summary=(
                f"No persisted research context snapshot{date_context}. "
                "This command reads persisted research data only."
            ),
            warnings=["No live calculation was performed."],
        )

    return CommandResult(
        status=_snapshot_status(snapshot.quality),
        title=f"/market-regime — {snapshot.as_of_date.isoformat()}",
        summary="Persisted research context; no live calculation was performed.",
        panels=[
            ResultPanel(
                title="Regime Summary",
                content={
                    "As of": snapshot.as_of_date.isoformat(),
                    "Regime": snapshot.regime,
                    "Trend": snapshot.trend,
                    "Volatility": snapshot.volatility,
                    "Quality": snapshot.quality,
                    "Benchmark": snapshot.benchmark_symbol,
                    "Benchmark bar date": snapshot.benchmark_bar_date.isoformat(),
                    "Methodology": snapshot.methodology_version,
                    "Generated at": snapshot.generated_at.isoformat(),
                },
            ),
            ResultPanel(
                title="Breadth",
                content={
                    "Active": snapshot.breadth_active_count,
                    "Eligible": snapshot.breadth_eligible_count,
                    "Excluded": snapshot.breadth_excluded_count,
                    "Coverage": percentage(snapshot.breadth_coverage),
                    "Above MA20": percentage(snapshot.pct_above_ma20),
                    "Above MA50": percentage(snapshot.pct_above_ma50),
                    "Positive return 20D": percentage(snapshot.pct_positive_return20),
                },
            ),
            ResultPanel(
                title="Freshness",
                content={
                    "Benchmark bar date": snapshot.benchmark_bar_date.isoformat(),
                    "Freshness basis": snapshot.lineage.get("freshness_basis", "—"),
                    "Generated at": snapshot.generated_at.isoformat(),
                },
            ),
            ResultPanel(title="Quality", content={"Quality": snapshot.quality}),
            ResultPanel(title="Lineage", content=dict(snapshot.lineage)),
            caveat_panel(snapshot.caveats),
        ],
        artifacts=[
            ResultArtifact(
                name=f"market.get_regime:{snapshot.as_of_date.isoformat()}",
                data={
                    "tool": "market.get_regime",
                    "available": True,
                    "as_of_date": snapshot.as_of_date.isoformat(),
                    "artifact_refs": [
                        f"market_regime_snapshot:{snapshot.as_of_date.isoformat()}"
                    ],
                    "missing_data": [],
                    "caveats": list(snapshot.caveats),
                },
            )
        ],
        metadata={
            "research_view": "market_regime",
            "artifact_id": f"market.get_regime:{snapshot.as_of_date.isoformat()}",
            "subject": snapshot.benchmark_symbol,
            "as_of_date": snapshot.as_of_date.isoformat(),
            "workflow_status": "partial"
            if snapshot.quality != "COMPLETE"
            else "complete",
            "missing_data": [],
            "artifact_refs": [
                f"market_regime_snapshot:{snapshot.as_of_date.isoformat()}"
            ],
        },
        warnings=list(snapshot.caveats),
    )


def handle_sector_strength(parsed: ParsedCommand, conn=None, **kwargs) -> CommandResult:
    if conn is None:
        return CommandResult(
            status=CommandStatus.FAILED,
            title="/sector-strength",
            summary="No database connection.",
        )

    validate_command_input(parsed, {"date", "top"}, maximum_positionals=1)
    requested_date = _requested_date(parsed)
    if parsed.positional and "top" in parsed.options:
        raise CommandValidationError("--top is only valid without a symbol.")
    top = _top(parsed)
    if parsed.positional:
        return symbol_sector_strength(
            conn, normalize_symbol(parsed.positional[0]), requested_date
        )
    return _sector_strength_list(conn, requested_date, top)


def _sector_strength_list(
    conn: duckdb.DuckDBPyConnection, requested_date: str | None, top: int | None
) -> CommandResult:
    snapshots = (
        get_latest_sector_strength(conn)
        if requested_date is None
        else get_sector_strength_as_of(conn, requested_date)
    )
    if not snapshots:
        date_context = f" for {requested_date}" if requested_date else ""
        return CommandResult(
            status=CommandStatus.EMPTY_RESULT,
            title="/sector-strength",
            summary=(
                f"No persisted research context data{date_context}. "
                "This command reads persisted research data only."
            ),
            warnings=["No live calculation was performed."],
        )

    visible = snapshots[:top] if top is not None else snapshots
    return CommandResult(
        status=_collection_status(visible),
        title=f"/sector-strength — {visible[0].as_of_date.isoformat()}",
        summary="Persisted research context; no live calculation was performed.",
        tables=[sector_table(visible)],
        panels=sector_disclosure_panels(visible),
        artifacts=[
            ResultArtifact(
                name=f"sector.get_strength:{visible[0].as_of_date.isoformat()}",
                data={
                    "tool": "sector.get_strength",
                    "available": True,
                    "as_of_date": visible[0].as_of_date.isoformat(),
                    "artifact_refs": [
                        f"sector_strength_snapshot:{visible[0].as_of_date.isoformat()}"
                    ],
                    "missing_data": [],
                    "caveats": snapshot_warnings(visible),
                },
            )
        ],
        metadata={
            "research_view": "sector_strength",
            "artifact_id": f"sector.get_strength:{visible[0].as_of_date.isoformat()}",
            "subject": "SECTOR",
            "as_of_date": visible[0].as_of_date.isoformat(),
            "workflow_status": "partial"
            if any(snapshot.quality != "COMPLETE" for snapshot in visible)
            else "complete",
            "missing_data": [],
            "artifact_refs": [
                f"sector_strength_snapshot:{visible[0].as_of_date.isoformat()}"
            ],
        },
        warnings=snapshot_warnings(visible),
    )


def _requested_date(parsed: ParsedCommand) -> str | None:
    value = parsed.options.get("date")
    if value is None:
        return None
    if isinstance(value, bool):
        raise CommandValidationError("--date requires a YYYY-MM-DD value.")
    return normalize_date(value)


def _top(parsed: ParsedCommand) -> int | None:
    value = parsed.options.get("top")
    if value is None:
        return None
    if isinstance(value, bool):
        raise CommandValidationError("--top must be a positive integer.")
    try:
        top = int(value)
    except ValueError as exc:
        raise CommandValidationError("--top must be a positive integer.") from exc
    if top <= 0:
        raise CommandValidationError("--top must be a positive integer.")
    return top


def _snapshot_status(quality: str) -> CommandStatus:
    return CommandStatus.SUCCESS if quality == "COMPLETE" else CommandStatus.PARTIAL


def _collection_status(snapshots: list[SectorStrengthSnapshot]) -> CommandStatus:
    return (
        CommandStatus.SUCCESS
        if all(snapshot.quality == "COMPLETE" for snapshot in snapshots)
        else CommandStatus.PARTIAL
    )
