from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MaintenanceStageStatus(str, Enum):
    PLANNED = "PLANNED"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class MaintenanceRunStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NOOP = "NOOP"


@dataclass(frozen=True, slots=True)
class DailyMaintenanceRequest:
    date: str | None = None
    symbols: tuple[str, ...] | None = None
    source: str | None = None
    dry_run: bool = False


@dataclass(frozen=True, slots=True)
class MaintenanceStageResult:
    name: str
    status: MaintenanceStageStatus
    counts: dict[str, int] = field(default_factory=dict)
    failures: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    diagnostics_refs: tuple[str, ...] = ()
    remediation: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status.value,
            "counts": self.counts,
            "failures": list(self.failures),
            "warnings": list(self.warnings),
            "diagnostics_refs": list(self.diagnostics_refs),
            "remediation": list(self.remediation),
        }


@dataclass(frozen=True, slots=True)
class DailyMaintenanceResult:
    status: MaintenanceRunStatus
    requested_date: str | None
    resolved_date: str
    correlation_id: str
    stages: tuple[MaintenanceStageResult, ...]
    requested_symbols: tuple[str, ...]
    successful_symbols: tuple[str, ...]
    failed_symbols: tuple[str, ...]
    diagnostics_refs: tuple[str, ...]
    mutated: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "status": self.status.value,
            "requested_date": self.requested_date,
            "resolved_date": self.resolved_date,
            "effective_session": self.resolved_date,
            "correlation_id": self.correlation_id,
            "stages": [stage.to_dict() for stage in self.stages],
            "counts": {
                "requested_symbols": len(self.requested_symbols),
                "successful_symbols": len(self.successful_symbols),
                "failed_symbols": len(self.failed_symbols),
            },
            "requested_symbols": list(self.requested_symbols),
            "successful_symbols": list(self.successful_symbols),
            "failed_symbols": list(self.failed_symbols),
            "diagnostics_refs": list(self.diagnostics_refs),
            "mutated": self.mutated,
        }


__all__ = [
    "DailyMaintenanceRequest",
    "DailyMaintenanceResult",
    "MaintenanceRunStatus",
    "MaintenanceStageResult",
    "MaintenanceStageStatus",
]
