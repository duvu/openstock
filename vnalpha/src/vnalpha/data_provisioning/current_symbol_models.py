from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TypedDict

from vnalpha.data_availability.deep_readiness_models import ReadinessResult


class ProvisioningOutcome(str, Enum):
    READY = "READY"
    REUSED = "REUSED"
    REFRESHED = "REFRESHED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ProvisioningAction:
    action: str
    status: str
    dataset: str | None = None
    symbol: str | None = None
    failure_category: str | None = None
    root_cause: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    source: str | None = None
    ingestion_run_id: str | None = None

    def to_dict(self) -> dict[str, str]:
        payload = {"action": self.action, "status": self.status}
        if self.dataset is not None:
            payload["dataset"] = self.dataset
        if self.symbol is not None:
            payload["symbol"] = self.symbol
        if self.failure_category is not None:
            payload["failure_category"] = self.failure_category
        if self.root_cause is not None:
            payload["root_cause"] = self.root_cause
        if self.start_date is not None:
            payload["start_date"] = self.start_date
        if self.end_date is not None:
            payload["end_date"] = self.end_date
        if self.source is not None:
            payload["source"] = self.source
        if self.ingestion_run_id is not None:
            payload["ingestion_run_id"] = self.ingestion_run_id
        return payload


class CurrentSymbolTrace(TypedDict):
    symbol: str
    outcome: str
    correlation_id: str
    requested_date: str
    resolved_date: str
    reused_fresh_data: bool
    refreshed: bool
    actions: list[dict[str, str]]
    warnings: list[str]
    errors: list[str]
    remediation: list[str]


@dataclass(frozen=True, slots=True)
class CurrentSymbolReadyResult:
    symbol: str
    outcome: ProvisioningOutcome
    correlation_id: str
    requested_date: str | None
    resolved_date: str
    actions: tuple[ProvisioningAction, ...]
    reused_fresh_data: bool
    refreshed: bool
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    remediation: tuple[str, ...] = ()
    readiness: ReadinessResult | None = field(default=None, repr=False)

    @property
    def is_ready(self) -> bool:
        return self.outcome in {
            ProvisioningOutcome.READY,
            ProvisioningOutcome.REUSED,
            ProvisioningOutcome.REFRESHED,
        }

    def to_trace_dict(self) -> CurrentSymbolTrace:
        return {
            "symbol": self.symbol,
            "outcome": self.outcome.value,
            "correlation_id": self.correlation_id,
            "requested_date": self.requested_date or "latest",
            "resolved_date": self.resolved_date,
            "reused_fresh_data": self.reused_fresh_data,
            "refreshed": self.refreshed,
            "actions": [action.to_dict() for action in self.actions],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "remediation": list(self.remediation),
        }
