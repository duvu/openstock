"""Fail-closed readiness for the persisted deep-analysis core contract."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import duckdb

from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
from vnalpha.data_availability.models import (
    EnsureDataAction,
    EnsureDataResult,
    EnsureDataStatus,
)
from vnalpha.data_availability.policy import DEFAULT_POLICY
from vnalpha.observability.audit import log_audit
from vnalpha.observability.context import get_correlation_id, set_correlation_id


class ReadinessArtifactStatus(str, Enum):
    READY = "READY"
    PROVISIONED = "PROVISIONED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NOT_REQUESTED = "NOT_REQUESTED"


@dataclass(frozen=True, slots=True)
class ReadinessArtifact:
    name: str
    status: ReadinessArtifactStatus
    actions: tuple[str, ...]
    freshness: str
    lineage: tuple[str, ...]
    error: str | None
    remediation: str | None


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

    def to_panel_dict(self) -> dict[str, str | list[dict[str, str | None]]]:
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
                    "error": artifact.error,
                    "remediation": artifact.remediation,
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


@dataclass(frozen=True, slots=True)
class DeepAnalysisReadinessService:
    ensure: Callable[[duckdb.DuckDBPyConnection, str, str | None], EnsureDataResult] = (
        ensure_symbol_analysis_ready
    )

    def ensure_ready(
        self,
        request: DeepAnalysisReadinessRequest,
    ) -> ReadinessResult:
        try:
            result = self.ensure(request.conn, request.symbol, request.requested_date)
        except (duckdb.Error, OSError, ValueError):
            result = EnsureDataResult(
                symbol=request.symbol.upper().strip(),
                target_date=request.requested_date or "latest",
                status=EnsureDataStatus.FAILED,
                errors=["Core data readiness could not be evaluated."],
            )
        correlation_id = _correlation_id()
        actions = tuple(action.value for action in result.actions_taken)
        artifacts = _artifacts(result, actions)
        errors = tuple(result.errors)
        if not result.is_ready and not errors:
            errors = ("Required deep-analysis data could not be made ready.",)
        readiness = ReadinessResult(
            symbol=result.symbol,
            requested_date=request.requested_date,
            resolved_date=result.target_date,
            artifacts=artifacts,
            actions=actions,
            warnings=tuple(result.warnings),
            errors=errors,
            correlation_id=correlation_id,
        )
        _audit_readiness(readiness)
        return readiness


def ensure_deep_analysis_ready(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    requested_date: str | None,
) -> ReadinessResult:
    return DeepAnalysisReadinessService().ensure_ready(
        DeepAnalysisReadinessRequest(conn, symbol, requested_date)
    )


def _artifacts(
    result: EnsureDataResult, actions: tuple[str, ...]
) -> tuple[ReadinessArtifact, ...]:
    failed_artifacts = _failed_artifact_names(result)
    specifications = (
        (
            "symbol_master",
            (EnsureDataAction.SYMBOLS_SYNCED,),
            _symbol_ready(result),
            "vnalpha data download symbols",
        ),
        (
            "canonical_ohlcv",
            (EnsureDataAction.OHLCV_SYNCED, EnsureDataAction.CANONICAL_BUILT),
            result.canonical_bars >= DEFAULT_POLICY.min_required_bars,
            f"vnalpha data download ohlcv {result.symbol}",
        ),
        (
            "benchmark_ohlcv",
            (
                EnsureDataAction.BENCHMARK_SYNCED,
                EnsureDataAction.BENCHMARK_CANONICAL_BUILT,
            ),
            not _mentions_benchmark_failure(result),
            f"vnalpha data download index {DEFAULT_POLICY.benchmark}",
        ),
        (
            "feature_snapshot",
            (EnsureDataAction.FEATURES_BUILT,),
            result.feature_snapshot_exists,
            f"vnalpha data build features {result.symbol} --date {result.target_date}",
        ),
        (
            "candidate_score",
            (EnsureDataAction.SCORED,),
            result.candidate_score_exists,
            f"vnalpha data build score {result.symbol} --date {result.target_date}",
        ),
    )
    return tuple(
        _artifact(
            name,
            result,
            actions,
            provision_actions,
            available,
            remediation,
            failed_artifacts,
        )
        for name, provision_actions, available, remediation in specifications
    )


def _artifact(
    name: str,
    result: EnsureDataResult,
    actions: tuple[str, ...],
    provision_actions: tuple[EnsureDataAction, ...],
    available: bool,
    remediation: str,
    failed_artifacts: frozenset[str],
) -> ReadinessArtifact:
    relevant_actions = tuple(
        action.value for action in provision_actions if action.value in actions
    )
    status = _artifact_status(
        name, result, available, relevant_actions, failed_artifacts
    )
    error = (
        None
        if status
        in {ReadinessArtifactStatus.READY, ReadinessArtifactStatus.PROVISIONED}
        else _artifact_error(name, result)
    )
    return ReadinessArtifact(
        name=name,
        status=status,
        actions=relevant_actions,
        freshness=result.freshness,
        lineage=tuple(result.lineage_actions),
        error=error,
        remediation=None if error is None else remediation,
    )


def _artifact_status(
    name: str,
    result: EnsureDataResult,
    available: bool,
    actions: tuple[str, ...],
    failed_artifacts: frozenset[str],
) -> ReadinessArtifactStatus:
    if name in failed_artifacts or not available:
        return ReadinessArtifactStatus.FAILED
    return (
        ReadinessArtifactStatus.PROVISIONED
        if actions
        else ReadinessArtifactStatus.READY
    )


def _artifact_error(name: str, result: EnsureDataResult) -> str:
    reason = next(
        (
            reason
            for reason in result.cache_rejection_reasons
            if _REJECTION_ARTIFACTS.get(reason) == name
        ),
        None,
    )
    if reason is not None:
        return f"{_artifact_label(name)} remains incomplete: {reason}."
    detail = next(iter(result.errors or result.warnings), "ensure did not complete")
    return f"Required {name} is unavailable: {detail}"


_REJECTION_ARTIFACTS = {
    "score_missing": "candidate_score",
    "score_stale": "candidate_score",
    "quality_unacceptable": "candidate_score",
    "lineage_incomplete": "candidate_score",
    "feature_snapshot_missing": "feature_snapshot",
    "canonical_history_insufficient": "canonical_ohlcv",
    "benchmark_history_insufficient": "benchmark_ohlcv",
}


def _failed_artifact_names(result: EnsureDataResult) -> frozenset[str]:
    if result.is_ready:
        return frozenset()
    failed = {
        _REJECTION_ARTIFACTS[reason]
        for reason in result.cache_rejection_reasons
        if reason in _REJECTION_ARTIFACTS
    }
    messages = (*result.errors, *result.warnings)
    if any("symbol_master" in message.lower() for message in messages):
        failed.add("symbol_master")
    if _ensure_did_not_evaluate_core_contract(result, messages):
        return frozenset(_REJECTION_ARTIFACTS.values()) | frozenset({"symbol_master"})
    return frozenset(failed)


def _ensure_did_not_evaluate_core_contract(
    result: EnsureDataResult, messages: tuple[str, ...]
) -> bool:
    return result.status is EnsureDataStatus.FAILED or any(
        "another ensure flow is active" in message.lower() for message in messages
    )


def _artifact_label(name: str) -> str:
    return name.replace("_", " ").capitalize()


def _symbol_ready(result: EnsureDataResult) -> bool:
    return not any("symbol_master" in message for message in result.errors)


def _mentions_benchmark_failure(result: EnsureDataResult) -> bool:
    return any(
        "benchmark" in message.lower() for message in (*result.errors, *result.warnings)
    )


def _correlation_id() -> str:
    correlation_id = get_correlation_id()
    return correlation_id if correlation_id != "unset" else set_correlation_id()


def _audit_readiness(readiness: ReadinessResult) -> None:
    log_audit(
        "DEEP_ANALYSIS_READINESS_STARTED",
        f"Deep-analysis readiness started for {readiness.symbol}.",
        extra={
            "symbol": readiness.symbol,
            "requested_date": readiness.requested_date,
            "resolved_date": readiness.resolved_date,
            "correlation_id": readiness.correlation_id,
        },
    )
    for artifact in readiness.artifacts:
        log_audit(
            "DEEP_ANALYSIS_READINESS_ARTIFACT",
            f"{artifact.name} is {artifact.status.value} for {readiness.symbol}.",
            status=artifact.status.value,
            level="ERROR" if artifact.error else "INFO",
            extra={
                "symbol": readiness.symbol,
                "requested_date": readiness.requested_date,
                "resolved_date": readiness.resolved_date,
                "correlation_id": readiness.correlation_id,
                "artifact": artifact.name,
                "actions": list(artifact.actions),
                "failed": artifact.error is not None,
            },
        )
    audit_extra = {
        "symbol": readiness.symbol,
        "resolved_date": readiness.resolved_date,
        "correlation_id": readiness.correlation_id,
        "actions": list(readiness.actions),
    }
    if EnsureDataAction.CACHE_HIT.value in readiness.actions:
        log_audit(
            "DEEP_ANALYSIS_READINESS_CACHE_HIT",
            f"Deep-analysis readiness used a cache hit for {readiness.symbol}.",
            status="OK",
            extra=audit_extra,
        )
    if readiness.warnings:
        log_audit(
            "DEEP_ANALYSIS_READINESS_PARTIAL",
            f"Deep-analysis readiness has caveats for {readiness.symbol}.",
            status="PARTIAL",
            level="WARNING",
            extra=audit_extra,
        )
    if not readiness.is_ready:
        log_audit(
            "DEEP_ANALYSIS_READINESS_FAILED",
            f"Deep-analysis readiness failed for {readiness.symbol}.",
            status="FAILED",
            level="ERROR",
            extra={**audit_extra, "error_count": len(readiness.errors)},
        )
    log_audit(
        "DEEP_ANALYSIS_READINESS_COMPLETED",
        f"Deep-analysis readiness {'completed' if readiness.is_ready else 'failed'} for {readiness.symbol}.",
        status="OK" if readiness.is_ready else "FAILED",
        level="INFO" if readiness.is_ready else "ERROR",
        extra={
            **audit_extra,
            "error_count": len(readiness.errors),
        },
    )
