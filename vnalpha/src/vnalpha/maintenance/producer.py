from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum
from hashlib import sha256
from json import dumps, loads
from pathlib import Path
from typing import Final
from uuid import uuid4

from vnalpha.core.dates import resolve_market_session_date
from vnalpha.data_availability.artifact_readiness import ArtifactReadinessService
from vnalpha.data_availability.artifact_readiness_models import (
    ArtifactReadinessRequest,
    ArtifactState,
    ReadinessCapability,
)
from vnalpha.ingestion.trading_calendar import VietnamSessionCalendar
from vnalpha.observability.context import get_correlation_id, set_correlation_id
from vnalpha.provisioning_queue import (
    DEFAULT_QUEUE_PATH,
    EnsureCurrentSymbolGoal,
    ProvisioningJobId,
    ProvisioningQueue,
    QueueDataset,
    QueueEntityType,
    RefreshMode,
    SyncDatasetRangeGoal,
    goal_identity,
)
from vnalpha.provisioning_queue.models import (
    SUPPORTED_SOURCE_POLICY_VERSION,
    ProvisioningGoal,
)
from vnalpha.warehouse.connection import read_connection
from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

_PRODUCER_SOFTWARE_VERSION: Final = "maintenance-producer-v1"
_DATASET_CONTRACT_VERSION: Final = "dataset-range-v1"
_CURRENT_SYMBOL_CONTRACT_VERSION: Final = "current-symbol-v1"


class MaintenanceRunState(StrEnum):
    ENQUEUING = "ENQUEUING"
    ACQUIRING = "ACQUIRING"
    FINALIZATION_QUEUED = "FINALIZATION_QUEUED"
    FINALIZING = "FINALIZING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class MaintenanceProducerError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _FrozenMaintenanceScope:
    run_id: str
    state: MaintenanceRunState
    resolved_session: str
    universe_snapshot_id: str
    universe_hash: str
    symbols: tuple[str, ...]
    goals: tuple[ProvisioningGoal, ...]
    source_policy_version: str
    calendar_version: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class MaintenanceProducerRequest:
    date: str | None = None
    universe: str = "VN30"
    snapshot_id: str | None = None
    maintenance_run_id: str | None = None
    source_policy_version: str = SUPPORTED_SOURCE_POLICY_VERSION
    priority: int = 0
    correlation_id: str | None = None


@dataclass(frozen=True, slots=True)
class MaintenanceProducerResult:
    maintenance_run_id: str
    state: MaintenanceRunState
    resolved_session: str
    universe_snapshot_id: str
    universe_hash: str
    symbols: tuple[str, ...]
    expected_count: int
    submitted_count: int
    joined_count: int
    mapped_count: int
    benchmark_job_id: ProvisioningJobId | None
    symbol_job_ids: tuple[tuple[str, ProvisioningJobId], ...]
    source_policy_version: str
    calendar_version: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class MaintenanceProducer:
    warehouse_path: Path | str | None = None
    queue_path: Path = DEFAULT_QUEUE_PATH
    calendar: VietnamSessionCalendar = VietnamSessionCalendar()

    def produce(self, request: MaintenanceProducerRequest) -> MaintenanceProducerResult:
        scope = self._prepare_run(request)
        queue = ProvisioningQueue(self.queue_path)
        queue.initialize()
        submitted = 0
        joined = 0
        mapped = 0
        for goal in scope.goals:
            identity = goal_identity(goal)
            existing = self._mapped_job(scope.run_id, identity)
            if existing is not None:
                mapped += 1
                continue
            recovered = queue.find_by_identity(
                identity,
                origin="maintenance",
                correlation_id=scope.correlation_id,
            )
            if recovered is not None:
                self._map_job(scope.run_id, goal, recovered.job_id)
                mapped += 1
                continue
            submission = queue.submit_or_join(
                goal,
                priority=request.priority,
                origin="maintenance",
                correlation_id=scope.correlation_id,
            )
            submitted += 0 if submission.joined_existing_job else 1
            joined += 1 if submission.joined_existing_job else 0
            self._map_job(scope.run_id, goal, submission.job.job_id)
            mapped += 1
        state = scope.state
        if mapped == len(scope.goals) and state is MaintenanceRunState.ENQUEUING:
            self._set_state(scope.run_id, MaintenanceRunState.ACQUIRING)
            state = MaintenanceRunState.ACQUIRING
        job_ids = self._job_ids(scope.run_id)
        benchmark_job_id = job_ids.get("VNINDEX")
        symbol_jobs = tuple(
            (symbol, job_ids[symbol]) for symbol in scope.symbols if symbol in job_ids
        )
        return MaintenanceProducerResult(
            maintenance_run_id=scope.run_id,
            state=state,
            resolved_session=scope.resolved_session,
            universe_snapshot_id=scope.universe_snapshot_id,
            universe_hash=scope.universe_hash,
            symbols=scope.symbols,
            expected_count=len(scope.goals),
            submitted_count=submitted,
            joined_count=joined,
            mapped_count=mapped,
            benchmark_job_id=benchmark_job_id,
            symbol_job_ids=symbol_jobs,
            source_policy_version=scope.source_policy_version,
            calendar_version=scope.calendar_version,
            correlation_id=scope.correlation_id,
        )

    def _prepare_run(
        self,
        request: MaintenanceProducerRequest,
    ) -> _FrozenMaintenanceScope:
        if request.maintenance_run_id is not None:
            return self._resumed_scope(request.maintenance_run_id)
        correlation_id = _correlation_id(request.correlation_id)
        resolved_session = resolve_market_session_date(request.date)
        session = date.fromisoformat(resolved_session)
        if request.source_policy_version != SUPPORTED_SOURCE_POLICY_VERSION:
            raise MaintenanceProducerError(
                "Unsupported maintenance source-policy version."
            )
        if not self.calendar.is_session(session):
            raise MaintenanceProducerError(
                "Maintenance requires a configured market session."
            )
        with read_connection(self.warehouse_path) as connection:
            snapshot_id, symbols = _frozen_symbols(
                connection,
                request.universe,
                request.snapshot_id,
            )
        goals = _remaining_goals(
            warehouse_path=self.warehouse_path,
            resolved_session=resolved_session,
            symbols=symbols,
            source_policy_version=request.source_policy_version,
        )
        universe_hash = _universe_hash(symbols)
        run_id = f"maint_{uuid4().hex[:12]}"
        with WarehouseWriteCoordinator(
            path=self.warehouse_path
        ).transaction() as connection:
            persisted_snapshot_id, persisted_symbols = _frozen_symbols(
                connection,
                request.universe,
                request.snapshot_id,
            )
            if persisted_snapshot_id != snapshot_id or persisted_symbols != symbols:
                raise MaintenanceProducerError(
                    "Frozen universe changed before maintenance run persistence."
                )
            now = datetime.now(timezone.utc)
            connection.execute(
                "INSERT INTO maintenance_run (run_id, correlation_id, requested_date, resolved_date, status, requested_symbol_count, successful_symbol_count, failed_symbol_count, started_at, completed_at, duration_seconds, software_version, calendar_version, mutated, diagnostics_refs, source_policy, universe_snapshot_id, universe_hash, symbols_json, expected_goals_json, source_policy_version) VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?, 0, ?, ?, FALSE, ?, ?, ?, ?, ?, ?, ?)",
                [
                    run_id,
                    correlation_id,
                    request.date,
                    resolved_session,
                    MaintenanceRunState.ENQUEUING.value,
                    len(symbols),
                    now,
                    now,
                    _PRODUCER_SOFTWARE_VERSION,
                    self.calendar.version,
                    "[]",
                    dumps({"version": request.source_policy_version}),
                    snapshot_id,
                    universe_hash,
                    dumps(list(symbols)),
                    dumps([goal.model_dump(mode="json") for goal in goals]),
                    request.source_policy_version,
                ],
            )
            for goal in goals:
                connection.execute(
                    "INSERT INTO maintenance_run_job (maintenance_run_id, goal_identity, goal_type, entity_id, goal_payload_json) VALUES (?, ?, ?, ?, ?)",
                    [
                        run_id,
                        goal_identity(goal),
                        goal.goal_type.value,
                        _entity_id(goal),
                        goal.payload_json(),
                    ],
                )
            return _FrozenMaintenanceScope(
                run_id=run_id,
                state=MaintenanceRunState.ENQUEUING,
                resolved_session=resolved_session,
                universe_snapshot_id=snapshot_id,
                universe_hash=universe_hash,
                symbols=symbols,
                goals=goals,
                source_policy_version=request.source_policy_version,
                calendar_version=self.calendar.version,
                correlation_id=correlation_id,
            )

    def _resumed_scope(self, maintenance_run_id: str) -> _FrozenMaintenanceScope:
        with WarehouseWriteCoordinator(
            path=self.warehouse_path
        ).transaction() as connection:
            row = connection.execute(
                "SELECT status, resolved_date, universe_snapshot_id, universe_hash, symbols_json, expected_goals_json, source_policy_version, calendar_version, correlation_id FROM maintenance_run WHERE run_id = ?",
                [maintenance_run_id],
            ).fetchone()
        if row is None:
            raise MaintenanceProducerError("Unknown maintenance run.")
        return _FrozenMaintenanceScope(
            run_id=maintenance_run_id,
            state=MaintenanceRunState(str(row[0])),
            resolved_session=str(row[1]),
            universe_snapshot_id=str(row[2]),
            universe_hash=str(row[3]),
            symbols=tuple(loads(row[4])),
            goals=tuple(_goal_from_payload(payload) for payload in loads(row[5])),
            source_policy_version=str(row[6]),
            calendar_version=str(row[7]),
            correlation_id=str(row[8]),
        )

    def _mapped_job(self, run_id: str, identity: str) -> ProvisioningJobId | None:
        with WarehouseWriteCoordinator(
            path=self.warehouse_path
        ).transaction() as connection:
            row = connection.execute(
                "SELECT job_id FROM maintenance_run_job WHERE maintenance_run_id = ? AND goal_identity = ?",
                [run_id, identity],
            ).fetchone()
        return None if row is None or row[0] is None else ProvisioningJobId(str(row[0]))

    def _map_job(
        self, run_id: str, goal: ProvisioningGoal, job_id: ProvisioningJobId
    ) -> None:
        with WarehouseWriteCoordinator(
            path=self.warehouse_path
        ).transaction() as connection:
            connection.execute(
                "UPDATE maintenance_run_job SET job_id = ?, mapped_at = current_timestamp WHERE maintenance_run_id = ? AND goal_identity = ? AND job_id IS NULL",
                [str(job_id), run_id, goal_identity(goal)],
            )

    def _set_state(self, run_id: str, state: MaintenanceRunState) -> None:
        with WarehouseWriteCoordinator(
            path=self.warehouse_path
        ).transaction() as connection:
            connection.execute(
                "UPDATE maintenance_run SET status = ? WHERE run_id = ?",
                [state.value, run_id],
            )

    def _job_ids(self, run_id: str) -> dict[str, ProvisioningJobId]:
        with WarehouseWriteCoordinator(
            path=self.warehouse_path
        ).transaction() as connection:
            rows = connection.execute(
                "SELECT entity_id, job_id FROM maintenance_run_job WHERE maintenance_run_id = ? AND job_id IS NOT NULL",
                [run_id],
            ).fetchall()
        return {str(entity): ProvisioningJobId(str(job_id)) for entity, job_id in rows}


def _frozen_symbols(
    connection, universe: str, snapshot_id: str | None
) -> tuple[str, tuple[str, ...]]:
    normalized_universe = universe.strip().upper()
    if snapshot_id is None:
        row = connection.execute(
            "SELECT snapshot_id FROM reference_membership_snapshot WHERE dataset = 'reference.membership' AND membership_type = 'universe' AND entity_id = ? AND status IN ('SUCCESS', 'PASS') AND snapshot_semantics = 'frozen' ORDER BY observed_at DESC LIMIT 1",
            [normalized_universe],
        ).fetchone()
        if row is not None:
            snapshot_id = str(row[0])
    if snapshot_id is not None:
        snapshot = connection.execute(
            "SELECT dataset, membership_type, entity_id, status, snapshot_semantics FROM reference_membership_snapshot WHERE snapshot_id = ?",
            [snapshot_id],
        ).fetchone()
        valid_snapshot = snapshot is not None and (
            str(snapshot[0]) == "reference.membership"
            and str(snapshot[1]) == "universe"
            and str(snapshot[2]) == normalized_universe
            and str(snapshot[3]) in {"SUCCESS", "PASS"}
            and str(snapshot[4]) == "frozen"
        )
        if not valid_snapshot:
            raise MaintenanceProducerError(
                "Requested universe snapshot is not a successful frozen universe."
            )
        rows = connection.execute(
            "SELECT member_symbol FROM reference_membership_member WHERE snapshot_id = ? ORDER BY member_symbol",
            [snapshot_id],
        ).fetchall()
        symbols = tuple(
            str(row[0]).strip().upper() for row in rows if str(row[0]).strip()
        )
        if symbols:
            return snapshot_id, symbols
    raise MaintenanceProducerError(
        "No acceptable frozen universe snapshot is available."
    )


def _goals(
    resolved_session: str,
    symbols: tuple[str, ...],
    source_policy_version: str,
    *,
    include_benchmark: bool = True,
) -> tuple[ProvisioningGoal, ...]:
    session = date.fromisoformat(resolved_session)
    benchmark = SyncDatasetRangeGoal(
        dataset=QueueDataset.INDEX_OHLCV,
        entity_type=QueueEntityType.INDEX,
        entity_id="VNINDEX",
        start_date=session,
        end_date=session,
        source_policy_version=source_policy_version,
        contract_version=_DATASET_CONTRACT_VERSION,
    )
    equities = tuple(
        EnsureCurrentSymbolGoal(
            symbol=symbol,
            effective_date=session,
            desired_capability=ReadinessCapability.PRICE_ANALYSIS,
            refresh_mode=RefreshMode.CACHE_FIRST,
            source_policy_version=source_policy_version,
            contract_version=_CURRENT_SYMBOL_CONTRACT_VERSION,
        )
        for symbol in symbols
    )
    return ((benchmark,) if include_benchmark else ()) + equities


def _remaining_goals(
    *,
    warehouse_path: Path | str | None,
    resolved_session: str,
    symbols: tuple[str, ...],
    source_policy_version: str,
) -> tuple[ProvisioningGoal, ...]:
    readiness = ArtifactReadinessService(warehouse_path)
    reports = tuple(
        readiness.inspect(
            ArtifactReadinessRequest(
                symbol=symbol,
                effective_date=resolved_session,
                capability=ReadinessCapability.PRICE_ANALYSIS,
            )
        )
        for symbol in symbols
    )
    missing_symbols = tuple(
        report.symbol for report in reports if not report.requested_ready
    )
    benchmark_ready = bool(reports) and all(
        any(
            artifact.name == "benchmark_ohlcv" and artifact.state is ArtifactState.READY
            for artifact in report.artifacts
        )
        for report in reports
    )
    return _goals(
        resolved_session,
        missing_symbols,
        source_policy_version,
        include_benchmark=not benchmark_ready,
    )


def _goal_from_payload(payload: dict[str, object]) -> ProvisioningGoal:
    goal_type = str(payload.get("goal_type"))
    if goal_type == "SYNC_DATASET_RANGE":
        return SyncDatasetRangeGoal.model_validate(payload)
    if goal_type == "ENSURE_CURRENT_SYMBOL":
        return EnsureCurrentSymbolGoal.model_validate(payload)
    raise MaintenanceProducerError("Unsupported persisted maintenance goal type.")


def _entity_id(goal: ProvisioningGoal) -> str:
    return "VNINDEX" if isinstance(goal, SyncDatasetRangeGoal) else goal.symbol


def _universe_hash(symbols: tuple[str, ...]) -> str:
    return sha256(dumps(list(symbols), separators=(",", ":")).encode()).hexdigest()


def _correlation_id(requested: str | None) -> str:
    if requested:
        return set_correlation_id(parent=requested)
    current = get_correlation_id()
    return current if current and current != "unset" else set_correlation_id()


__all__ = [
    "MaintenanceProducer",
    "MaintenanceProducerError",
    "MaintenanceProducerRequest",
    "MaintenanceProducerResult",
    "MaintenanceRunState",
]
