from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from json import JSONDecodeError, loads
from pathlib import Path
from typing import Final, Mapping

import duckdb

from vnalpha.company_context import (
    CompanyContextResult,
    CompanyContextStatus,
    get_current_company_context,
)
from vnalpha.data_availability.artifact_readiness import ArtifactReadinessService
from vnalpha.data_availability.artifact_readiness_models import (
    ArtifactReadinessReport,
    ArtifactReadinessRequest,
    ReadinessCapability,
)
from vnalpha.data_availability.policy import DataAvailabilityPolicy
from vnalpha.data_provisioning.current_symbol_queue_wait import (
    CurrentSymbolWaitMode,
    default_current_symbol_wait_timeout_seconds,
    wait_for_terminal,
)
from vnalpha.data_provisioning.current_symbol_result import (
    CurrentSymbolProvisioningState,
    CurrentSymbolResearchResult,
    CurrentSymbolResearchStatus,
)
from vnalpha.data_provisioning.current_symbol_result import (
    build_result as _result,
)
from vnalpha.data_provisioning.current_symbol_result import (
    terminal_result as _terminal_result,
)
from vnalpha.observability.context import get_correlation_id, set_correlation_id
from vnalpha.provisioning_queue.models import (
    EnsureCurrentSymbolGoal,
    GoalEnrichment,
    RefreshMode,
)
from vnalpha.provisioning_queue.repository import ProvisioningQueue
from vnalpha.warehouse.connection import WarehouseOpenError, read_connection

_SOURCE_POLICY_VERSION: Final = "policy-v1"
_CURRENT_SYMBOL_CONTRACT_VERSION: Final = "current-symbol-v1"


@dataclass(frozen=True, slots=True)
class CurrentSymbolResearchRequest:
    symbol: str
    effective_date: str | None
    requested_capability: ReadinessCapability
    priority: int = 1
    force_refresh: bool = False
    historical: bool = False
    wait_mode: CurrentSymbolWaitMode = CurrentSymbolWaitMode.WAIT_UP_TO
    wait_timeout_seconds: float = field(
        default_factory=default_current_symbol_wait_timeout_seconds
    )
    origin: str | None = None
    correlation_id: str | None = None
    requested_enrichments: tuple[GoalEnrichment, ...] = ()


@dataclass(frozen=True, slots=True)
class CurrentSymbolResearchApplication:
    """Inspect persisted evidence before optionally submitting one typed queue goal."""

    warehouse_path: Path | str | None = None
    queue_path: Path | None = None
    policy: DataAvailabilityPolicy = field(default_factory=DataAvailabilityPolicy)

    def execute(
        self, request: CurrentSymbolResearchRequest
    ) -> CurrentSymbolResearchResult:
        correlation_id = _correlation_id(request.correlation_id)
        readiness = self._inspect(request)
        refresh_company_context = (
            GoalEnrichment.COMPANY_CONTEXT in request.requested_enrichments
        )
        if (
            readiness.requested_ready
            and not request.force_refresh
            and not refresh_company_context
        ):
            return self._with_company_context(
                _result(
                    status=CurrentSymbolResearchStatus.READY,
                    readiness=readiness,
                    job_id=None,
                    correlation_id=correlation_id,
                ),
                request,
            )
        if (
            readiness.effective_capability is not None
            and not request.force_refresh
            and not readiness.should_enqueue
            and not refresh_company_context
        ):
            return self._with_company_context(
                _result(
                    status=CurrentSymbolResearchStatus.DEGRADED,
                    readiness=readiness,
                    job_id=None,
                    correlation_id=correlation_id,
                ),
                request,
            )
        if request.historical or not (
            readiness.should_enqueue or request.force_refresh or refresh_company_context
        ):
            return self._with_company_context(
                _result(
                    status=CurrentSymbolResearchStatus.UNAVAILABLE,
                    readiness=readiness,
                    job_id=None,
                    correlation_id=correlation_id,
                ),
                request,
            )
        queue = self._queue()
        queue.initialize()
        submission = queue.submit_or_join(
            _goal_from(request, readiness),
            priority=request.priority,
            origin=request.origin,
            correlation_id=correlation_id,
        )
        job = wait_for_terminal(
            queue,
            submission.job,
            request.wait_mode,
            request.wait_timeout_seconds,
        )
        if job.is_terminal:
            terminal = _terminal_result(
                readiness=self._inspect(request),
                job_id=job.job_id,
                correlation_id=correlation_id,
                succeeded=job.status.value == "SUCCEEDED",
            )
            refresh_outcome = _company_context_outcome(job.result)
            if refresh_company_context and refresh_outcome is not None:
                return replace(terminal, company_context=refresh_outcome)
            return self._with_company_context(terminal, request)
        if (
            readiness.effective_capability is not None
            and request.wait_mode is CurrentSymbolWaitMode.DETACH
        ):
            return self._with_company_context(
                _result(
                    status=CurrentSymbolResearchStatus.DEGRADED,
                    readiness=readiness,
                    job_id=job.job_id,
                    correlation_id=correlation_id,
                ),
                request,
            )
        return self._with_company_context(
            _result(
                status=(
                    CurrentSymbolResearchStatus.PENDING
                    if submission.joined_existing_job
                    or request.wait_mode is not CurrentSymbolWaitMode.DETACH
                    else CurrentSymbolResearchStatus.ACCEPTED
                ),
                readiness=readiness,
                job_id=job.job_id,
                correlation_id=correlation_id,
            ),
            request,
        )

    def _inspect(
        self, request: CurrentSymbolResearchRequest
    ) -> ArtifactReadinessReport:
        return ArtifactReadinessService(
            warehouse_path=self.warehouse_path,
            policy=self.policy,
        ).inspect(
            ArtifactReadinessRequest(
                symbol=request.symbol,
                effective_date=request.effective_date,
                capability=request.requested_capability,
                historical=request.historical,
            )
        )

    def _queue(self) -> ProvisioningQueue:
        if self.queue_path is None:
            return ProvisioningQueue()
        return ProvisioningQueue(self.queue_path)

    def _with_company_context(
        self,
        result: CurrentSymbolResearchResult,
        request: CurrentSymbolResearchRequest,
    ) -> CurrentSymbolResearchResult:
        if request.historical:
            context = CompanyContextResult(
                CompanyContextStatus.HISTORICAL_UNAVAILABLE,
                None,
            )
        else:
            try:
                with read_connection(self.warehouse_path) as connection:
                    context = get_current_company_context(
                        connection,
                        result.readiness.symbol,
                        historical=False,
                    )
            except (WarehouseOpenError, duckdb.Error, OSError):
                context = CompanyContextResult(CompanyContextStatus.UNAVAILABLE, None)
        return replace(result, company_context=context)


def _goal_from(
    request: CurrentSymbolResearchRequest, readiness: ArtifactReadinessReport
) -> EnsureCurrentSymbolGoal:
    return EnsureCurrentSymbolGoal(
        symbol=readiness.symbol,
        effective_date=date.fromisoformat(readiness.effective_date),
        desired_capability=request.requested_capability,
        allowed_fallback=readiness.fallback_capability,
        refresh_mode=(
            RefreshMode.FORCE_REFRESH
            if request.force_refresh
            else RefreshMode.CACHE_FIRST
        ),
        source_policy_version=_SOURCE_POLICY_VERSION,
        contract_version=_CURRENT_SYMBOL_CONTRACT_VERSION,
        requested_enrichments=request.requested_enrichments,
    )


def _correlation_id(requested: str | None) -> str:
    if requested:
        return set_correlation_id(parent=requested)
    current = get_correlation_id()
    if current and current != "unset":
        return current
    return set_correlation_id()


def _company_context_outcome(result: str | None) -> CompanyContextResult | None:
    if result is None:
        return None
    try:
        payload = loads(result)
    except JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None
    return CompanyContextResult.from_dict(payload)


__all__ = [
    "CurrentSymbolResearchApplication",
    "CurrentSymbolResearchRequest",
    "CurrentSymbolResearchResult",
    "CurrentSymbolResearchStatus",
    "CurrentSymbolProvisioningState",
    "CurrentSymbolWaitMode",
]
