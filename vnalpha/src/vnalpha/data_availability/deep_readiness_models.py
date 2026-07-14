"""Typed result contracts for fail-closed deep-analysis readiness."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import duckdb

from vnalpha.data_availability.models import JsonValue


class ReadinessArtifactStatus(str, Enum):
    READY = "READY"
    PROVISIONED = "PROVISIONED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NOT_REQUESTED = "NOT_REQUESTED"


class RemediationAction(str, Enum):
    SYNC_SYMBOLS = "SYNC_SYMBOLS"
    SYNC_OHLCV = "SYNC_OHLCV"
    BUILD_CANONICAL = "BUILD_CANONICAL"
    SYNC_BENCHMARK = "SYNC_BENCHMARK"
    BUILD_FEATURES = "BUILD_FEATURES"
    SCORE_SYMBOL = "SCORE_SYMBOL"


@dataclass(frozen=True, slots=True)
class RemediationStep:
    action: RemediationAction
    artifact: str
    command_surface: str
    command: str
    description: str
    required: bool


@dataclass(frozen=True, slots=True)
class ReadinessArtifact:
    name: str
    status: ReadinessArtifactStatus
    actions: tuple[str, ...]
    freshness: str
    lineage: tuple[str, ...]
    error: str | None
    remediation: str | None
    available: bool = False
    requested_date: str | None = None
    resolved_date: str | None = None
    observed_as_of_date: str | None = None
    row_count: int | None = None
    required_row_count: int | None = None
    window_start_date: str | None = None
    quality_status: str = "unknown"
    lineage_status: str = "unknown"
    provider: str | None = None
    ingestion_run_id: str | None = None
    generated_at: str | None = None
    methodology_version: str | None = None
    feature_build_version: str | None = None
    scoring_version: str | None = None
    benchmark_as_of_date: str | None = None
    benchmark_row_count: int | None = None
    source_symbol: str | None = None
    symbol_metadata: tuple[tuple[str, str], ...] = ()
    error_code: str | None = None
    remediation_steps: tuple[RemediationStep, ...] = ()


@dataclass(frozen=True, slots=True)
class DeepAnalysisReadinessRequest:
    conn: duckdb.DuckDBPyConnection
    symbol: str
    requested_date: str | None


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    symbol: str
    requested_date: str | None
    resolved_date: str
    artifacts: tuple[ReadinessArtifact, ...]
    actions: tuple[str, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    correlation_id: str

    @property
    def is_ready(self) -> bool:
        return not self.errors and all(
            artifact.status
            in {ReadinessArtifactStatus.READY, ReadinessArtifactStatus.PROVISIONED}
            for artifact in self.artifacts
        )

    def to_panel_dict(self) -> dict[str, JsonValue]:
        return {
            "requested_date": self.requested_date or "latest",
            "resolved_date": self.resolved_date,
            "correlation_id": self.correlation_id,
            "status": "READY" if self.is_ready else "FAILED",
            "artifacts": [
                {
                    "name": artifact.name,
                    "status": artifact.status.value,
                    "actions": ", ".join(artifact.actions) or "—",
                    "freshness": artifact.freshness,
                    "lineage": ", ".join(artifact.lineage) or "—",
                    "available": artifact.available,
                    "requested_date": artifact.requested_date,
                    "resolved_date": artifact.resolved_date,
                    "observed_as_of_date": artifact.observed_as_of_date,
                    "row_count": artifact.row_count,
                    "required_row_count": artifact.required_row_count,
                    "window_start_date": artifact.window_start_date,
                    "quality_status": artifact.quality_status,
                    "lineage_status": artifact.lineage_status,
                    "provider": artifact.provider,
                    "ingestion_run_id": artifact.ingestion_run_id,
                    "generated_at": artifact.generated_at,
                    "methodology_version": artifact.methodology_version,
                    "feature_build_version": artifact.feature_build_version,
                    "scoring_version": artifact.scoring_version,
                    "benchmark_as_of_date": artifact.benchmark_as_of_date,
                    "benchmark_row_count": artifact.benchmark_row_count,
                    "source_symbol": artifact.source_symbol,
                    "symbol_metadata": dict(artifact.symbol_metadata),
                    "error_code": artifact.error_code,
                    "error": artifact.error,
                    "remediation": artifact.remediation,
                    "remediation_steps": [
                        {
                            "action": step.action.value,
                            "artifact": step.artifact,
                            "command_surface": step.command_surface,
                            "command": step.command,
                            "description": step.description,
                            "required": step.required,
                        }
                        for step in artifact.remediation_steps
                    ],
                }
                for artifact in self.artifacts
            ],
        }

    def failure_summary(self) -> str:
        failed = [artifact for artifact in self.artifacts if artifact.error]
        if failed:
            return failed[0].error or "Required deep-analysis data is unavailable."
        if self.errors:
            return self.errors[0]
        return "Required deep-analysis data is unavailable."
