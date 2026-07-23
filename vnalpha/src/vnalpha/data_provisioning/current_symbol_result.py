from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

from vnalpha.company_context import CompanyContextResult
from vnalpha.data_availability.artifact_readiness_models import (
    ArtifactReadinessReport,
    ReadinessCapability,
)
from vnalpha.provisioning_queue.queue_models import ProvisioningJobId


class CurrentSymbolResearchStatus(StrEnum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    ACCEPTED = "ACCEPTED"
    PENDING = "PENDING"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class CurrentSymbolProvisioningState(StrEnum):
    REUSED = "REUSED"
    QUEUED = "QUEUED"
    COMPLETED = "COMPLETED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class CurrentSymbolResearchResult:
    status: CurrentSymbolResearchStatus
    requested_capability: ReadinessCapability
    effective_capability: ReadinessCapability | None
    requested_date: str | None
    effective_date: str
    job_id: ProvisioningJobId | None
    provisioning: CurrentSymbolProvisioningState
    reused_fresh_data: bool
    correlation_id: str
    readiness: ArtifactReadinessReport
    company_context: CompanyContextResult | None = None


def build_result(
    *,
    status: CurrentSymbolResearchStatus,
    readiness: ArtifactReadinessReport,
    job_id: ProvisioningJobId | None,
    correlation_id: str,
) -> CurrentSymbolResearchResult:
    match status:
        case CurrentSymbolResearchStatus.READY:
            capability = readiness.requested_capability
            reused_fresh_data = job_id is None
        case CurrentSymbolResearchStatus.DEGRADED:
            capability = readiness.effective_capability
            reused_fresh_data = job_id is None
        case (
            CurrentSymbolResearchStatus.ACCEPTED
            | CurrentSymbolResearchStatus.PENDING
            | CurrentSymbolResearchStatus.UNAVAILABLE
            | CurrentSymbolResearchStatus.FAILED
        ):
            capability = None
            reused_fresh_data = False
        case unreachable:
            assert_never(unreachable)
    return CurrentSymbolResearchResult(
        status=status,
        requested_capability=readiness.requested_capability,
        effective_capability=capability,
        requested_date=readiness.requested_date,
        effective_date=readiness.effective_date,
        job_id=job_id,
        provisioning=provisioning_state(status, job_id),
        reused_fresh_data=reused_fresh_data,
        correlation_id=correlation_id,
        readiness=readiness,
    )


def terminal_result(
    *,
    readiness: ArtifactReadinessReport,
    job_id: ProvisioningJobId,
    correlation_id: str,
    succeeded: bool,
) -> CurrentSymbolResearchResult:
    if succeeded and readiness.requested_ready:
        status = CurrentSymbolResearchStatus.READY
    elif succeeded and readiness.effective_capability is not None:
        status = CurrentSymbolResearchStatus.DEGRADED
    elif succeeded:
        status = CurrentSymbolResearchStatus.UNAVAILABLE
    else:
        status = CurrentSymbolResearchStatus.FAILED
    return build_result(
        status=status,
        readiness=readiness,
        job_id=job_id,
        correlation_id=correlation_id,
    )


def provisioning_state(
    status: CurrentSymbolResearchStatus,
    job_id: ProvisioningJobId | None,
) -> CurrentSymbolProvisioningState:
    match status:
        case CurrentSymbolResearchStatus.READY | CurrentSymbolResearchStatus.DEGRADED:
            return (
                CurrentSymbolProvisioningState.COMPLETED
                if job_id is not None
                else CurrentSymbolProvisioningState.REUSED
            )
        case CurrentSymbolResearchStatus.ACCEPTED | CurrentSymbolResearchStatus.PENDING:
            return CurrentSymbolProvisioningState.QUEUED
        case CurrentSymbolResearchStatus.UNAVAILABLE:
            return CurrentSymbolProvisioningState.UNAVAILABLE
        case CurrentSymbolResearchStatus.FAILED:
            return CurrentSymbolProvisioningState.FAILED
        case unreachable:
            assert_never(unreachable)
