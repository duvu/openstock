from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import duckdb

from vnalpha.core.dates import resolve_date
from vnalpha.data_availability.deep_readiness_artifacts import build_artifacts
from vnalpha.data_availability.deep_readiness_audit import (
    audit_ensure_exception,
    audit_readiness,
    audit_started,
    correlation_id,
)
from vnalpha.data_availability.deep_readiness_models import (
    DeepAnalysisReadinessRequest,
    ReadinessResult,
)
from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
from vnalpha.data_availability.models import EnsureDataResult, EnsureDataStatus


@dataclass(frozen=True, slots=True)
class DeepAnalysisReadinessService:
    ensure: Callable[[duckdb.DuckDBPyConnection, str, str | None], EnsureDataResult] = (
        ensure_symbol_analysis_ready
    )

    def ensure_ready(self, request: DeepAnalysisReadinessRequest) -> ReadinessResult:
        current_correlation_id = correlation_id()
        resolved_date = resolve_date(request.requested_date, conn=request.conn)
        normalized_symbol = request.symbol.upper().strip()
        audit_started(
            symbol=normalized_symbol,
            requested_date=request.requested_date,
            resolved_date=resolved_date,
            correlation_id=current_correlation_id,
        )
        result = self._ensure_result(
            request=request,
            symbol=normalized_symbol,
            resolved_date=resolved_date,
            correlation_id=current_correlation_id,
        )
        actions = tuple(action.value for action in result.actions_taken)
        errors = tuple(result.errors)
        if not result.is_ready and not errors:
            errors = ("Required deep-analysis data could not be made ready.",)
        readiness = ReadinessResult(
            symbol=result.symbol,
            requested_date=request.requested_date,
            resolved_date=resolved_date,
            artifacts=build_artifacts(
                result=result,
                actions=actions,
                requested_date=request.requested_date,
                resolved_date=resolved_date,
            ),
            actions=actions,
            warnings=_sanitized_warnings(result.warnings),
            errors=errors,
            correlation_id=current_correlation_id,
        )
        audit_readiness(readiness)
        return readiness

    def _ensure_result(
        self,
        *,
        request: DeepAnalysisReadinessRequest,
        symbol: str,
        resolved_date: str,
        correlation_id: str,
    ) -> EnsureDataResult:
        try:
            return self.ensure(request.conn, symbol, resolved_date)
        except Exception as exc:  # noqa: BROAD_EXCEPT_OK
            audit_ensure_exception(
                symbol=symbol,
                requested_date=request.requested_date,
                resolved_date=resolved_date,
                correlation_id=correlation_id,
                exception_type=type(exc).__name__,
            )
            return EnsureDataResult(
                symbol=symbol,
                target_date=resolved_date,
                status=EnsureDataStatus.FAILED,
                errors=["Core data readiness could not be evaluated."],
            )


def ensure_deep_analysis_ready(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    requested_date: str | None,
) -> ReadinessResult:
    return DeepAnalysisReadinessService().ensure_ready(
        DeepAnalysisReadinessRequest(conn, symbol, requested_date)
    )


def _sanitized_warnings(warnings: list[str]) -> tuple[str, ...]:
    return tuple(_sanitized_warning(warning) for warning in warnings)


def _sanitized_warning(warning: str) -> str:
    prefix, separator, _detail = warning.partition(" failed")
    if separator:
        return f"{prefix} failed during readiness."
    return warning
