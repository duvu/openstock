from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Final

import duckdb

from vnalpha.data_provisioning.service import (
    DataProvisioningRequest,
    DataProvisioningResult,
    DataProvisioningService,
)
from vnalpha.maintenance.daily import DailyMaintenanceService
from vnalpha.maintenance.models import MaintenanceStageResult, MaintenanceStageStatus
from vnalpha.provisioning_queue.models import FinalizeMarketSessionGoal
from vnalpha.research_intelligence.group_context import (
    GroupContextProjector,
    build_group_context,
)
from vnalpha.symbol_memory.selective_projection import SelectiveSymbolMemoryProjector

_BENCHMARK: Final = "VNINDEX"
_STAGES: Final = (
    "finalization-coverage",
    "finalization-features",
    "finalization-score-watchlist",
    "finalization-context",
    "finalization-outcomes",
    "finalization-memory",
    "finalization-result",
)
_REQUIRED_STAGES: Final = frozenset(_STAGES[1:-1])


@dataclass(frozen=True, slots=True)
class FinalizationStageOutcome:
    succeeded: bool
    detail: str


@dataclass(frozen=True, slots=True)
class FinalizationPolicy:
    version: str
    minimum_coverage: float
    required_stages: frozenset[str]


DEFAULT_FINALIZATION_POLICY: Final = FinalizationPolicy(
    version="finalization-policy-v1",
    minimum_coverage=0.80,
    required_stages=_REQUIRED_STAGES,
)


class SessionFinalizer:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self._connection = connection

    def execute(
        self, goal: FinalizeMarketSessionGoal, stage_name: str
    ) -> FinalizationStageOutcome:
        if stage_name not in _STAGES:
            raise ValueError("unsupported finalization stage")
        scope = self._scope(goal)
        if stage_name != _STAGES[0] and not self._coverage_is_sufficient(goal):
            return FinalizationStageOutcome(False, "FINALIZATION_COVERAGE_UNAVAILABLE")
        existing = self._existing_stage(goal.maintenance_run_id, stage_name)
        if existing is MaintenanceStageStatus.SUCCESS:
            return FinalizationStageOutcome(True, f"{stage_name}: REUSED")
        match stage_name:
            case "finalization-coverage":
                result = self._coverage_stage(goal, scope)
            case "finalization-features":
                result = self._provisioning_stage(
                    stage_name,
                    DataProvisioningRequest(
                        "build",
                        "features",
                        symbols=scope.eligible_symbols,
                        date=scope.resolved_session.isoformat(),
                        benchmark=_BENCHMARK,
                    ),
                )
            case "finalization-score-watchlist":
                result = self._provisioning_stage(
                    stage_name,
                    DataProvisioningRequest(
                        "build",
                        "score",
                        symbols=scope.eligible_symbols,
                        date=scope.resolved_session.isoformat(),
                    ),
                )
            case "finalization-context":
                result = self._context_stage(scope)
            case "finalization-outcomes":
                result = DailyMaintenanceService(
                    self._connection
                )._mature_candidate_outcomes(scope.resolved_session.isoformat())
                result = MaintenanceStageResult(
                    stage_name,
                    result.status,
                    counts=result.counts,
                    failures=result.failures,
                    warnings=result.warnings,
                    diagnostics_refs=result.diagnostics_refs,
                    remediation=result.remediation,
                )
            case "finalization-memory":
                result = self._memory_stage(scope)
            case "finalization-result":
                result = self._result_stage(goal, scope)
            case unreachable:
                raise AssertionError(f"unreachable finalization stage: {unreachable}")
        self._persist_stage(goal.maintenance_run_id, stage_name, result)
        if result.status is MaintenanceStageStatus.FAILED:
            self._persist_failed_run(goal.maintenance_run_id, scope, result)
            return FinalizationStageOutcome(False, f"{stage_name}: FAILED")
        return FinalizationStageOutcome(True, f"{stage_name}: {result.status.value}")

    def _scope(self, goal: FinalizeMarketSessionGoal) -> _FinalizationScope:
        row = self._connection.execute(
            "SELECT resolved_date, universe_hash, symbols_json, correlation_id "
            "FROM maintenance_run "
            "WHERE run_id = ?",
            [goal.maintenance_run_id],
        ).fetchone()
        if row is None:
            raise ValueError("unknown maintenance run")
        resolved_session = date.fromisoformat(str(row[0]))
        if (
            resolved_session != goal.resolved_session
            or str(row[1]) != goal.frozen_universe_hash
        ):
            raise ValueError(
                "finalization goal does not match frozen maintenance scope"
            )
        symbols = tuple(str(symbol) for symbol in json.loads(str(row[2])))
        eligible_symbols = tuple(
            symbol
            for symbol in symbols
            if self._canonical_reaches(symbol, resolved_session)
        )
        return _FinalizationScope(
            resolved_session=resolved_session,
            symbols=symbols,
            eligible_symbols=eligible_symbols,
            benchmark_ready=self._canonical_reaches(_BENCHMARK, resolved_session),
            correlation_id=str(row[3]),
        )

    def _coverage_stage(
        self, goal: FinalizeMarketSessionGoal, scope: _FinalizationScope
    ) -> MaintenanceStageResult:
        self._connection.execute(
            "UPDATE maintenance_run SET status = ? WHERE run_id = ?",
            ["FINALIZING", goal.maintenance_run_id],
        )
        coverage = scope.coverage
        failures = ()
        if not scope.benchmark_ready:
            failures = ("Frozen-session benchmark canonical evidence is unavailable.",)
        elif coverage < DEFAULT_FINALIZATION_POLICY.minimum_coverage:
            failures = (
                "Frozen eligible coverage "
                f"{coverage:.3f} is below "
                f"{DEFAULT_FINALIZATION_POLICY.minimum_coverage:.3f}.",
            )
        return MaintenanceStageResult(
            "finalization-coverage",
            (
                MaintenanceStageStatus.FAILED
                if failures
                else MaintenanceStageStatus.PARTIAL
                if len(scope.eligible_symbols) != len(scope.symbols)
                else MaintenanceStageStatus.SUCCESS
            ),
            counts={
                "frozen_symbols": len(scope.symbols),
                "eligible_symbols": len(scope.eligible_symbols),
                "excluded_symbols": len(scope.symbols) - len(scope.eligible_symbols),
                "coverage_percent": int(coverage * 100),
                "benchmark_ready": int(scope.benchmark_ready),
            },
            failures=failures,
            warnings=(f"finalization policy={DEFAULT_FINALIZATION_POLICY.version}",),
        )

    def _provisioning_stage(
        self, stage_name: str, request: DataProvisioningRequest
    ) -> MaintenanceStageResult:
        result = DataProvisioningService(self._connection).execute(request)
        return _stage_from_provisioning(stage_name, result)

    def _context_stage(self, scope: _FinalizationScope) -> MaintenanceStageResult:
        results = (
            self._provisioning_stage(
                "market-regime",
                DataProvisioningRequest(
                    "build", "market-regime", date=scope.resolved_session.isoformat()
                ),
            ),
            self._provisioning_stage(
                "sector-strength",
                DataProvisioningRequest(
                    "build", "sector-strength", date=scope.resolved_session.isoformat()
                ),
            ),
        )
        try:
            group_result = build_group_context(self._connection, scope.resolved_session)
            group_stage = MaintenanceStageResult(
                "group-context",
                (
                    MaintenanceStageStatus.SUCCESS
                    if group_result.snapshots
                    else MaintenanceStageStatus.PARTIAL
                ),
                counts={"snapshots": len(group_result.snapshots)},
                warnings=group_result.caveats,
            )
        except (duckdb.Error, ValueError) as error:
            group_stage = MaintenanceStageResult(
                "group-context", MaintenanceStageStatus.FAILED, failures=(str(error),)
            )
        return _combined_stage("finalization-context", (*results, group_stage))

    def _memory_stage(self, scope: _FinalizationScope) -> MaintenanceStageResult:
        symbol_result = SelectiveSymbolMemoryProjector(self._connection).project(
            scope.eligible_symbols,
            as_of_date=scope.resolved_session,
            correlation_id=scope.correlation_id,
        )
        entity_result = GroupContextProjector(self._connection).project(
            scope.resolved_session, correlation_id=scope.correlation_id
        )
        failures = tuple(
            f"Symbol memory failed for {symbol}."
            for symbol in symbol_result.failed_symbols
        ) + tuple(
            f"Entity memory failed for {entity}."
            for entity in entity_result.failed_entities
        )
        return MaintenanceStageResult(
            "finalization-memory",
            (
                MaintenanceStageStatus.PARTIAL
                if failures
                else MaintenanceStageStatus.SUCCESS
            ),
            counts={
                "symbols_processed": len(symbol_result.processed_symbols),
                "entity_claims_created": entity_result.claims_created,
            },
            failures=failures,
        )

    def _result_stage(
        self, goal: FinalizeMarketSessionGoal, scope: _FinalizationScope
    ) -> MaintenanceStageResult:
        states = {
            name: self._existing_stage(goal.maintenance_run_id, name)
            for name in DEFAULT_FINALIZATION_POLICY.required_stages
        }
        failed = any(
            status is MaintenanceStageStatus.FAILED for status in states.values()
        )
        partial = any(
            status is MaintenanceStageStatus.PARTIAL for status in states.values()
        )
        status = (
            MaintenanceStageStatus.FAILED
            if failed
            else MaintenanceStageStatus.PARTIAL
            if partial or len(scope.eligible_symbols) != len(scope.symbols)
            else MaintenanceStageStatus.SUCCESS
        )
        self._connection.execute(
            "UPDATE maintenance_run SET status = ?, successful_symbol_count = ?, "
            "failed_symbol_count = ?, mutated = TRUE WHERE run_id = ?",
            [
                status.value,
                len(scope.eligible_symbols),
                len(scope.symbols) - len(scope.eligible_symbols),
                goal.maintenance_run_id,
            ],
        )
        return MaintenanceStageResult(
            "finalization-result",
            status,
            counts={
                "eligible_symbols": len(scope.eligible_symbols),
                "excluded_symbols": len(scope.symbols) - len(scope.eligible_symbols),
            },
        )

    def _persist_failed_run(
        self,
        run_id: str,
        scope: _FinalizationScope,
        stage: MaintenanceStageResult,
    ) -> None:
        self._connection.execute(
            "UPDATE maintenance_run SET status = 'FAILED', successful_symbol_count = ?, "
            "failed_symbol_count = ? WHERE run_id = ?",
            [
                len(scope.eligible_symbols),
                len(scope.symbols) - len(scope.eligible_symbols),
                run_id,
            ],
        )

    def _existing_stage(
        self, run_id: str, stage_name: str
    ) -> MaintenanceStageStatus | None:
        row = self._connection.execute(
            "SELECT status FROM maintenance_finalization_stage WHERE stage_run_id = ?",
            [_stage_id(run_id, stage_name)],
        ).fetchone()
        return None if row is None else MaintenanceStageStatus(str(row[0]))

    def _coverage_is_sufficient(self, goal: FinalizeMarketSessionGoal) -> bool:
        return self._existing_stage(goal.maintenance_run_id, _STAGES[0]) in {
            MaintenanceStageStatus.SUCCESS,
            MaintenanceStageStatus.PARTIAL,
        }

    def _persist_stage(
        self, run_id: str, stage_name: str, stage: MaintenanceStageResult
    ) -> None:
        order = _STAGES.index(stage_name) + 1
        self._connection.execute(
            "INSERT INTO maintenance_finalization_stage (stage_run_id, run_id, stage_name, "
            "stage_order, status, counts, failures, warnings, diagnostics_refs, remediation, "
            "started_at, completed_at, duration_seconds) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "now(), now(), 0) ON CONFLICT(stage_run_id) DO UPDATE SET "
            "status = excluded.status, counts = excluded.counts, failures = excluded.failures, "
            "warnings = excluded.warnings, diagnostics_refs = excluded.diagnostics_refs, "
            "remediation = excluded.remediation, completed_at = now()",
            [
                _stage_id(run_id, stage_name),
                run_id,
                stage_name,
                order,
                stage.status.value,
                json.dumps(stage.counts),
                json.dumps(list(stage.failures)),
                json.dumps(list(stage.warnings)),
                json.dumps(list(stage.diagnostics_refs)),
                json.dumps(list(stage.remediation)),
            ],
        )

    def _canonical_reaches(self, symbol: str, session: date) -> bool:
        row = self._connection.execute(
            "SELECT MAX(CAST(time AS DATE)) FROM canonical_ohlcv "
            "WHERE symbol = ? AND interval = '1D'",
            [symbol],
        ).fetchone()
        return bool(row and row[0] is not None and row[0] >= session)


@dataclass(frozen=True, slots=True)
class _FinalizationScope:
    resolved_session: date
    symbols: tuple[str, ...]
    eligible_symbols: tuple[str, ...]
    benchmark_ready: bool
    correlation_id: str

    @property
    def coverage(self) -> float:
        return len(self.eligible_symbols) / len(self.symbols) if self.symbols else 0.0


def _stage_from_provisioning(
    stage_name: str, result: DataProvisioningResult
) -> MaintenanceStageResult:
    return MaintenanceStageResult(
        stage_name,
        MaintenanceStageStatus(result.status.value),
        counts=result.counts,
        failures=(result.error,) if result.error else (),
        warnings=result.warnings,
        remediation=(result.follow_up,) if result.follow_up else (),
    )


def _combined_stage(
    stage_name: str, stages: tuple[MaintenanceStageResult, ...]
) -> MaintenanceStageResult:
    statuses = {stage.status for stage in stages}
    status = (
        MaintenanceStageStatus.FAILED
        if MaintenanceStageStatus.FAILED in statuses
        else MaintenanceStageStatus.PARTIAL
        if MaintenanceStageStatus.PARTIAL in statuses
        else MaintenanceStageStatus.SUCCESS
    )
    counts: dict[str, int] = {}
    for stage in stages:
        for key, value in stage.counts.items():
            counts[key] = counts.get(key, 0) + value
    return MaintenanceStageResult(
        stage_name,
        status,
        counts=counts,
        failures=tuple(value for stage in stages for value in stage.failures),
        warnings=tuple(value for stage in stages for value in stage.warnings),
        remediation=tuple(value for stage in stages for value in stage.remediation),
    )


def _stage_id(run_id: str, stage_name: str) -> str:
    return f"{run_id}_{stage_name}"


__all__ = [
    "DEFAULT_FINALIZATION_POLICY",
    "FinalizationPolicy",
    "FinalizationStageOutcome",
    "SessionFinalizer",
]
