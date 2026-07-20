from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date as DateType

import duckdb

from vnalpha.core.dates import resolve_date
from vnalpha.data_availability.checks import compute_lookback_start
from vnalpha.data_availability.policy import DEFAULT_POLICY
from vnalpha.data_provisioning.service import (
    DataProvisioningRequest,
    DataProvisioningResult,
    DataProvisioningService,
    ProvisioningStatus,
)
from vnalpha.ingestion.models import SymbolIngestionStatus
from vnalpha.ingestion.trading_calendar import VietnamSessionCalendar
from vnalpha.maintenance.models import (
    DailyMaintenanceRequest,
    DailyMaintenanceResult,
    MaintenanceRunStatus,
    MaintenanceStageResult,
    MaintenanceStageStatus,
)
from vnalpha.observability.context import get_correlation_id, set_correlation_id
from vnalpha.research_intelligence.group_context import (
    GroupContextBuildResult,
    GroupContextProjector,
    GroupProjectionResult,
    build_group_context,
)
from vnalpha.symbol_memory.selective_projection import (
    SelectiveProjectionResult,
    SelectiveSymbolMemoryProjector,
)
from vnalpha.warehouse.repositories import get_symbols_active

_PLANNED_STAGES = (
    "resolve_session",
    "symbol_snapshot",
    "incremental_ohlcv",
    "benchmark_ohlcv",
    "gap_repair",
    "canonical",
    "features",
    "score_watchlist",
    "market_regime",
    "sector_strength",
    "group_context",
    "symbol_memory",
    "entity_memory",
)
_MAX_SYMBOL_SCOPE = 500


class DailyMaintenanceService:
    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        provisioning_factory: Callable[
            [duckdb.DuckDBPyConnection], DataProvisioningService
        ] = DataProvisioningService,
        calendar: VietnamSessionCalendar | None = None,
        memory_projector_factory: Callable[
            [duckdb.DuckDBPyConnection], SelectiveSymbolMemoryProjector
        ] = SelectiveSymbolMemoryProjector,
    ) -> None:
        self.conn = conn
        self.provisioning_factory = provisioning_factory
        self.calendar = calendar or VietnamSessionCalendar()
        self.memory_projector_factory = memory_projector_factory

    def run(self, request: DailyMaintenanceRequest) -> DailyMaintenanceResult:
        resolved_date = resolve_date(request.date)
        market_date = DateType.fromisoformat(resolved_date)
        correlation_id = _correlation_id()
        requested_symbols = _normalize_symbols(request.symbols)
        coverage = self.calendar.get_coverage_status(market_date)
        if coverage["is_expired"]:
            # Beyond the supported calendar horizon: fail closed rather than
            # silently treating every future weekday as a valid session (#254).
            return DailyMaintenanceResult(
                status=MaintenanceRunStatus.NOOP,
                requested_date=request.date,
                resolved_date=resolved_date,
                correlation_id=correlation_id,
                stages=(
                    MaintenanceStageResult(
                        "resolve_session",
                        MaintenanceStageStatus.SKIPPED,
                        warnings=(
                            f"Trading calendar {coverage['version']} does not cover "
                            f"{resolved_date}; supported through "
                            f"{coverage['valid_through']}.",
                        ),
                        remediation=(
                            "Update the Vietnam trading calendar with official "
                            "holiday data for the operating year before maintaining "
                            "dates beyond its validity horizon.",
                        ),
                    ),
                ),
                requested_symbols=requested_symbols,
                successful_symbols=(),
                failed_symbols=(),
                diagnostics_refs=(),
                mutated=False,
            )
        if not self.calendar.is_session(market_date):
            return DailyMaintenanceResult(
                status=MaintenanceRunStatus.NOOP,
                requested_date=request.date,
                resolved_date=resolved_date,
                correlation_id=correlation_id,
                stages=(
                    MaintenanceStageResult(
                        "resolve_session", MaintenanceStageStatus.SKIPPED
                    ),
                ),
                requested_symbols=requested_symbols,
                successful_symbols=(),
                failed_symbols=(),
                diagnostics_refs=(),
                mutated=False,
            )
        if request.dry_run:
            return DailyMaintenanceResult(
                status=MaintenanceRunStatus.SUCCESS,
                requested_date=request.date,
                resolved_date=resolved_date,
                correlation_id=correlation_id,
                stages=tuple(
                    MaintenanceStageResult(name, MaintenanceStageStatus.PLANNED)
                    for name in _PLANNED_STAGES
                ),
                requested_symbols=requested_symbols,
                successful_symbols=(),
                failed_symbols=(),
                diagnostics_refs=(),
                mutated=False,
            )
        return self._execute(
            request,
            resolved_date,
            market_date,
            correlation_id,
            requested_symbols,
        )

    def _execute(
        self,
        request: DailyMaintenanceRequest,
        resolved_date: str,
        market_date: DateType,
        correlation_id: str,
        requested_symbols: tuple[str, ...],
    ) -> DailyMaintenanceResult:
        service = self.provisioning_factory(self.conn)
        coverage = self.calendar.get_coverage_status(market_date)
        session_warnings: tuple[str, ...] = ()
        if coverage["near_expiry"]:
            session_warnings = (
                f"Trading calendar {coverage['version']} expires on "
                f"{coverage['valid_through']} ({coverage['days_remaining']} days "
                "remaining); refresh it with official holiday data for the next "
                "operating year.",
            )
        stages = [
            MaintenanceStageResult(
                "resolve_session",
                MaintenanceStageStatus.SUCCESS,
                warnings=session_warnings,
            )
        ]
        executed: list[DataProvisioningResult] = []
        if _has_current_symbol_snapshot(self.conn, market_date):
            stages.append(
                MaintenanceStageResult(
                    "symbol_snapshot", MaintenanceStageStatus.SKIPPED
                )
            )
        else:
            symbols_result = service.execute(
                DataProvisioningRequest("download", "symbols", source=request.source)
            )
            executed.append(symbols_result)
            stages.append(_stage("symbol_snapshot", (symbols_result,)))
            if symbols_result.status is ProvisioningStatus.FAILED:
                return _final_result(
                    request,
                    resolved_date,
                    correlation_id,
                    requested_symbols,
                    (),
                    requested_symbols,
                    stages,
                    executed,
                )

        scope = requested_symbols or tuple(get_symbols_active(self.conn))
        if not scope:
            stages.append(
                MaintenanceStageResult(
                    "incremental_ohlcv",
                    MaintenanceStageStatus.FAILED,
                    failures=("No active symbols were available for maintenance.",),
                )
            )
            return _final_result(
                request,
                resolved_date,
                correlation_id,
                scope,
                (),
                (),
                stages,
                executed,
            )

        current_symbols = tuple(
            symbol
            for symbol in scope
            if _canonical_reaches_date(self.conn, symbol, market_date)
        )
        sync_scope = tuple(symbol for symbol in scope if symbol not in current_symbols)
        if sync_scope:
            sync_result = service.execute(
                DataProvisioningRequest(
                    "sync",
                    "daily",
                    symbols=sync_scope,
                    date=resolved_date,
                    source=request.source,
                )
            )
            executed.append(sync_result)
            stages.append(_stage("incremental_ohlcv", (sync_result,)))
            synced_symbols, failed = _symbol_outcomes(sync_result, sync_scope)
            successful = (*current_symbols, *synced_symbols)
        else:
            stages.append(
                MaintenanceStageResult(
                    "incremental_ohlcv",
                    MaintenanceStageStatus.SKIPPED,
                    counts={"current": len(current_symbols)},
                )
            )
            successful = current_symbols
            failed = set()

        lookback_start = compute_lookback_start(
            resolved_date, DEFAULT_POLICY.lookback_days
        )
        if _canonical_reaches_date(self.conn, DEFAULT_POLICY.benchmark, market_date):
            benchmark_ready = True
            stages.append(
                MaintenanceStageResult(
                    "benchmark_ohlcv", MaintenanceStageStatus.SKIPPED
                )
            )
        else:
            benchmark_download = service.execute(
                DataProvisioningRequest(
                    "download",
                    "index",
                    symbol=DEFAULT_POLICY.benchmark,
                    start=lookback_start,
                    end=resolved_date,
                    source=request.source,
                )
            )
            executed.append(benchmark_download)
            benchmark_results = [benchmark_download]
            benchmark_ready = benchmark_download.status is ProvisioningStatus.SUCCESS
            if benchmark_ready:
                benchmark_canonical = service.execute(
                    DataProvisioningRequest(
                        "build", "canonical", symbol=DEFAULT_POLICY.benchmark
                    )
                )
                executed.append(benchmark_canonical)
                benchmark_results.append(benchmark_canonical)
                benchmark_ready = (
                    benchmark_canonical.status is ProvisioningStatus.SUCCESS
                )
            stages.append(_stage("benchmark_ohlcv", benchmark_results))

        eligible: list[str] = []
        gap_results: list[DataProvisioningResult] = []
        canonical_results: list[DataProvisioningResult] = []
        gap_start = self.calendar.rewind_sessions(market_date, 10).isoformat()
        for symbol in successful:
            gap_scan = service.execute(
                DataProvisioningRequest(
                    "gaps",
                    "ohlcv",
                    symbol=symbol,
                    start=gap_start,
                    end=resolved_date,
                )
            )
            executed.append(gap_scan)
            gap_results.append(gap_scan)
            if gap_scan.status is ProvisioningStatus.FAILED:
                failed.add(symbol)
                continue
            if gap_scan.counts.get("true_gaps", 0) > 0:
                repair = service.execute(
                    DataProvisioningRequest(
                        "repair",
                        "ohlcv",
                        symbol=symbol,
                        start=gap_start,
                        end=resolved_date,
                        source=request.source,
                    )
                )
                executed.append(repair)
                gap_results.append(repair)
                if repair.status is not ProvisioningStatus.SUCCESS:
                    failed.add(symbol)
                    continue
            canonical = service.execute(
                DataProvisioningRequest("build", "canonical", symbol=symbol)
            )
            executed.append(canonical)
            canonical_results.append(canonical)
            if canonical.status is ProvisioningStatus.SUCCESS:
                eligible.append(symbol)
            else:
                failed.add(symbol)
        stages.append(
            _stage("gap_repair", gap_results)
            if gap_results
            else MaintenanceStageResult("gap_repair", MaintenanceStageStatus.SKIPPED)
        )
        stages.append(
            _stage("canonical", canonical_results)
            if canonical_results
            else MaintenanceStageResult("canonical", MaintenanceStageStatus.SKIPPED)
        )

        downstream = tuple(symbol for symbol in eligible if symbol not in failed)
        if downstream and benchmark_ready:
            features = service.execute(
                DataProvisioningRequest(
                    "build",
                    "features",
                    symbols=downstream,
                    date=resolved_date,
                    benchmark=DEFAULT_POLICY.benchmark,
                )
            )
            executed.append(features)
            stages.append(_stage("features", (features,)))
            if features.status is not ProvisioningStatus.FAILED:
                score = service.execute(
                    DataProvisioningRequest(
                        "build", "score", symbols=downstream, date=resolved_date
                    )
                )
                executed.append(score)
                stages.append(_stage("score_watchlist", (score,)))
            else:
                stages.append(
                    MaintenanceStageResult(
                        "score_watchlist", MaintenanceStageStatus.SKIPPED
                    )
                )
        else:
            stages.extend(
                (
                    MaintenanceStageResult("features", MaintenanceStageStatus.SKIPPED),
                    MaintenanceStageResult(
                        "score_watchlist", MaintenanceStageStatus.SKIPPED
                    ),
                )
            )

        for name, artifact in (
            ("market_regime", "market-regime"),
            ("sector_strength", "sector-strength"),
        ):
            context = service.execute(
                DataProvisioningRequest("build", artifact, date=resolved_date)
            )
            executed.append(context)
            stages.append(_stage(name, (context,)))

        group_context: GroupContextBuildResult | None = None
        try:
            group_context = build_group_context(self.conn, market_date)
            stages.append(_group_context_stage(group_context))
        except (duckdb.Error, ValueError) as exc:
            stages.append(
                MaintenanceStageResult(
                    "group_context",
                    MaintenanceStageStatus.FAILED,
                    failures=(str(exc),),
                )
            )

        memory = self.memory_projector_factory(self.conn).project(
            downstream,
            as_of_date=market_date,
            correlation_id=correlation_id,
        )
        stages.append(_memory_stage(memory))

        if group_context is None:
            stages.append(
                MaintenanceStageResult("entity_memory", MaintenanceStageStatus.SKIPPED)
            )
        else:
            entity_memory = GroupContextProjector(self.conn).project(
                market_date, correlation_id=correlation_id
            )
            stages.append(_entity_memory_stage(entity_memory))

        successful_final = tuple(
            symbol for symbol in downstream if symbol not in failed
        )
        return _final_result(
            request,
            resolved_date,
            correlation_id,
            scope,
            successful_final,
            tuple(sorted(failed)),
            stages,
            executed,
        )


def _normalize_symbols(symbols: tuple[str, ...] | None) -> tuple[str, ...]:
    if symbols is None:
        return ()
    normalized = tuple(dict.fromkeys(symbol.strip().upper() for symbol in symbols))
    if any(not symbol for symbol in normalized):
        raise ValueError("Maintenance symbols must not be empty.")
    if len(normalized) > _MAX_SYMBOL_SCOPE:
        raise ValueError(f"Maintenance accepts at most {_MAX_SYMBOL_SCOPE} symbols.")
    return normalized


def _has_current_symbol_snapshot(
    conn: duckdb.DuckDBPyConnection, market_date: DateType
) -> bool:
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM symbol_source_snapshot "
            "WHERE snapshot_status = 'SUCCESS' AND CAST(completed_at AS DATE) = ?",
            [market_date],
        ).fetchone()
    except duckdb.Error:
        return False
    return bool(row and row[0])


def _canonical_reaches_date(
    conn: duckdb.DuckDBPyConnection, symbol: str, market_date: DateType
) -> bool:
    try:
        row = conn.execute(
            "SELECT MAX(CAST(time AS DATE)) FROM canonical_ohlcv "
            "WHERE symbol = ? AND interval = '1D'",
            [symbol],
        ).fetchone()
    except duckdb.Error:
        return False
    return bool(row and row[0] is not None and row[0] >= market_date)


def _symbol_outcomes(
    result: DataProvisioningResult, scope: tuple[str, ...]
) -> tuple[tuple[str, ...], set[str]]:
    if not result.symbol_results:
        if result.status is ProvisioningStatus.SUCCESS:
            return scope, set()
        return (), set(scope)
    successful = tuple(
        item.symbol
        for item in result.symbol_results
        if item.status in {SymbolIngestionStatus.SUCCESS, SymbolIngestionStatus.SKIPPED}
    )
    failed = {
        item.symbol for item in result.symbol_results if item.symbol not in successful
    }
    return successful, failed


def _stage(
    name: str, results: Iterable[DataProvisioningResult]
) -> MaintenanceStageResult:
    items = tuple(results)
    statuses = {item.status for item in items}
    if ProvisioningStatus.FAILED in statuses:
        status = (
            MaintenanceStageStatus.PARTIAL
            if len(statuses) > 1
            else MaintenanceStageStatus.FAILED
        )
    elif ProvisioningStatus.PARTIAL in statuses:
        status = MaintenanceStageStatus.PARTIAL
    else:
        status = MaintenanceStageStatus.SUCCESS
    counts: dict[str, int] = {}
    for item in items:
        for key, value in item.counts.items():
            counts[key] = counts.get(key, 0) + value
    return MaintenanceStageResult(
        name=name,
        status=status,
        counts=counts,
        failures=tuple(item.error for item in items if item.error),
        warnings=tuple(warning for item in items for warning in item.warnings),
        diagnostics_refs=_diagnostics_refs(items),
        remediation=tuple(item.follow_up for item in items if item.follow_up),
    )


def _diagnostics_refs(
    results: Iterable[DataProvisioningResult],
) -> tuple[str, ...]:
    refs = []
    for result in results:
        for symbol_result in result.symbol_results:
            if (
                symbol_result.diagnostics_ref
                and symbol_result.diagnostics_ref not in refs
            ):
                refs.append(symbol_result.diagnostics_ref)
    return tuple(refs)


def _memory_stage(result: SelectiveProjectionResult) -> MaintenanceStageResult:
    status = (
        MaintenanceStageStatus.PARTIAL
        if result.failed_symbols and result.processed_symbols
        else MaintenanceStageStatus.FAILED
        if result.failed_symbols
        else MaintenanceStageStatus.SUCCESS
    )
    return MaintenanceStageResult(
        name="symbol_memory",
        status=status,
        counts=result.counters.to_dict(),
        failures=(
            (f"Memory projection failed for {len(result.failed_symbols)} symbols.",)
            if result.failed_symbols
            else ()
        ),
    )


def _group_context_stage(result: GroupContextBuildResult) -> MaintenanceStageResult:
    return MaintenanceStageResult(
        name="group_context",
        status=(
            MaintenanceStageStatus.SUCCESS
            if result.snapshots
            else MaintenanceStageStatus.PARTIAL
        ),
        counts={
            "snapshots": len(result.snapshots),
            "unclassified": sum(result.unclassified_counts.values()),
        },
        warnings=result.caveats,
    )


def _entity_memory_stage(result: GroupProjectionResult) -> MaintenanceStageResult:
    return MaintenanceStageResult(
        name="entity_memory",
        status=(
            MaintenanceStageStatus.PARTIAL
            if result.failed_entities
            else MaintenanceStageStatus.SUCCESS
        ),
        counts={
            "claims_created": result.claims_created,
            "claims_superseded": result.claims_superseded,
            "cards_compacted": result.cards_compacted,
        },
        failures=tuple(
            f"Entity memory projection failed for {entity}."
            for entity in result.failed_entities
        ),
    )


def _final_result(
    request: DailyMaintenanceRequest,
    resolved_date: str,
    correlation_id: str,
    requested_symbols: tuple[str, ...],
    successful_symbols: tuple[str, ...],
    failed_symbols: tuple[str, ...],
    stages: list[MaintenanceStageResult],
    executed: list[DataProvisioningResult],
) -> DailyMaintenanceResult:
    failed_stages = sum(
        stage.status is MaintenanceStageStatus.FAILED for stage in stages
    )
    partial_stages = sum(
        stage.status is MaintenanceStageStatus.PARTIAL for stage in stages
    )
    if failed_stages and not successful_symbols:
        status = MaintenanceRunStatus.FAILED
    elif failed_stages or partial_stages or failed_symbols:
        status = MaintenanceRunStatus.PARTIAL
    else:
        status = MaintenanceRunStatus.SUCCESS
    return DailyMaintenanceResult(
        status=status,
        requested_date=request.date,
        resolved_date=resolved_date,
        correlation_id=correlation_id,
        stages=tuple(stages),
        requested_symbols=requested_symbols,
        successful_symbols=successful_symbols,
        failed_symbols=failed_symbols,
        diagnostics_refs=_diagnostics_refs(executed),
        mutated=bool(executed),
    )


def _correlation_id() -> str:
    current = get_correlation_id()
    if current and current != "unset":
        return current
    return set_correlation_id()


__all__ = [
    "DailyMaintenanceRequest",
    "DailyMaintenanceResult",
    "DailyMaintenanceService",
    "MaintenanceRunStatus",
    "MaintenanceStageStatus",
]
