from __future__ import annotations

from vnalpha.data_availability.deep_readiness_models import ReadinessResult
from vnalpha.data_availability.models import EnsureDataAction
from vnalpha.observability.audit import log_audit
from vnalpha.observability.context import get_correlation_id, set_correlation_id


def correlation_id() -> str:
    current = get_correlation_id()
    return current if current != "unset" else set_correlation_id()


def audit_started(
    *, symbol: str, requested_date: str | None, resolved_date: str, correlation_id: str
) -> None:
    log_audit(
        "DEEP_ANALYSIS_READINESS_STARTED",
        f"Deep-analysis readiness started for {symbol}.",
        extra={
            "symbol": symbol,
            "requested_date": requested_date,
            "resolved_date": resolved_date,
            "correlation_id": correlation_id,
        },
    )


def audit_ensure_exception(
    *,
    symbol: str,
    requested_date: str | None,
    resolved_date: str,
    correlation_id: str,
    exception_type: str,
) -> None:
    log_audit(
        "DEEP_ANALYSIS_READINESS_ENSURE_EXCEPTION",
        f"Deep-analysis readiness ensure failed for {symbol}.",
        status="FAILED",
        level="ERROR",
        extra={
            "symbol": symbol,
            "requested_date": requested_date,
            "resolved_date": resolved_date,
            "correlation_id": correlation_id,
            "exception_type": exception_type,
        },
    )


def audit_readiness(readiness: ReadinessResult) -> None:
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
    extra = {
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
            extra=extra,
        )
    if readiness.warnings:
        log_audit(
            "DEEP_ANALYSIS_READINESS_PARTIAL",
            f"Deep-analysis readiness has caveats for {readiness.symbol}.",
            status="PARTIAL",
            level="WARNING",
            extra=extra,
        )
    if not readiness.is_ready:
        log_audit(
            "DEEP_ANALYSIS_READINESS_FAILED",
            f"Deep-analysis readiness failed for {readiness.symbol}.",
            status="FAILED",
            level="ERROR",
            extra={**extra, "error_count": len(readiness.errors)},
        )
    log_audit(
        "DEEP_ANALYSIS_READINESS_COMPLETED",
        f"Deep-analysis readiness {'completed' if readiness.is_ready else 'failed'} for {readiness.symbol}.",
        status="OK" if readiness.is_ready else "FAILED",
        level="INFO" if readiness.is_ready else "ERROR",
        extra={**extra, "error_count": len(readiness.errors)},
    )
