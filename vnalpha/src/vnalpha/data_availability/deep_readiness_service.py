from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import duckdb

from vnalpha.core.dates import resolve_market_session_date
from vnalpha.data_availability.deep_context_failures import (
    unavailable_context_artifacts,
)
from vnalpha.data_availability.deep_context_readiness import (
    ContextReadinessInput,
    evaluate_context_readiness,
)
from vnalpha.data_availability.deep_readiness_artifacts import build_artifacts
from vnalpha.data_availability.deep_readiness_audit import (
    audit_ensure_exception,
    audit_readiness,
    audit_started,
    correlation_id,
)
from vnalpha.data_availability.deep_readiness_models import (
    ContextIssue,
    ContextRequirement,
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
        normalized_symbol = request.symbol.upper().strip()
        try:
            resolved_date = resolve_market_session_date(request.requested_date)
        except Exception as exc:  # noqa: BROAD_EXCEPT_OK
            return self._terminal_failure(
                symbol=normalized_symbol,
                requested_date=request.requested_date,
                resolved_date=request.requested_date or "unresolved",
                correlation_id=current_correlation_id,
                message="Deep-analysis date could not be resolved.",
                exception_type=type(exc).__name__,
            )

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
        try:
            core_artifacts = build_artifacts(
                result=result,
                actions=actions,
                requested_date=request.requested_date,
                resolved_date=resolved_date,
            )
        except Exception as exc:  # noqa: BROAD_EXCEPT_OK
            return self._terminal_failure(
                symbol=normalized_symbol,
                requested_date=request.requested_date,
                resolved_date=resolved_date,
                correlation_id=current_correlation_id,
                message="Core readiness evidence could not be evaluated.",
                exception_type=type(exc).__name__,
                start_already_recorded=True,
            )

        context_input = ContextReadinessInput(
            conn=request.conn,
            symbol=normalized_symbol,
            resolved_date=resolved_date,
            market_regime_requirement=request.market_regime_requirement,
            sector_strength_requirement=request.sector_strength_requirement,
            correlation_id=current_correlation_id,
        )
        try:
            context_artifacts = evaluate_context_readiness(context_input)
        except Exception:  # noqa: BROAD_EXCEPT_OK
            context_artifacts = unavailable_context_artifacts(
                context_input, ContextIssue.CONTEXT_BUILD_FAILED
            )

        artifacts = (*core_artifacts, *context_artifacts)
        errors = tuple(result.errors) + tuple(
            artifact.error
            for artifact in context_artifacts
            if artifact.error is not None
        )
        if not result.is_ready and not errors:
            errors = ("Required deep-analysis data could not be made ready.",)
        readiness = ReadinessResult(
            symbol=result.symbol,
            requested_date=request.requested_date,
            resolved_date=resolved_date,
            artifacts=artifacts,
            actions=actions,
            warnings=(
                *_sanitized_warnings(result.warnings),
                *(
                    artifact.error_code
                    for artifact in context_artifacts
                    if not artifact.blocking and artifact.error_code is not None
                ),
            ),
            errors=errors,
            correlation_id=current_correlation_id,
            action_outcomes=tuple(result.action_outcomes),
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

    def _terminal_failure(
        self,
        *,
        symbol: str,
        requested_date: str | None,
        resolved_date: str,
        correlation_id: str,
        message: str,
        exception_type: str,
        start_already_recorded: bool = False,
    ) -> ReadinessResult:
        if not start_already_recorded:
            audit_started(
                symbol=symbol,
                requested_date=requested_date,
                resolved_date=resolved_date,
                correlation_id=correlation_id,
            )
        audit_ensure_exception(
            symbol=symbol,
            requested_date=requested_date,
            resolved_date=resolved_date,
            correlation_id=correlation_id,
            exception_type=exception_type,
        )
        readiness = ReadinessResult(
            symbol=symbol,
            requested_date=requested_date,
            resolved_date=resolved_date,
            artifacts=(),
            actions=(),
            warnings=(),
            errors=(message,),
            correlation_id=correlation_id,
        )
        audit_readiness(readiness)
        return readiness


def ensure_deep_analysis_ready(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    requested_date: str | None,
    *,
    market_regime_requirement: ContextRequirement = ContextRequirement.NOT_REQUESTED,
    sector_strength_requirement: ContextRequirement = ContextRequirement.NOT_REQUESTED,
) -> ReadinessResult:
    return DeepAnalysisReadinessService().ensure_ready(
        DeepAnalysisReadinessRequest(
            conn,
            symbol,
            requested_date,
            market_regime_requirement,
            sector_strength_requirement,
        )
    )


def _sanitized_warnings(warnings: list[str]) -> tuple[str, ...]:
    return tuple(_sanitized_warning(warning) for warning in warnings)


def _sanitized_warning(warning: str) -> str:
    normalized = warning.casefold()
    if any(marker in normalized for marker in ("failed", "failure", "provider error")):
        return "A readiness action failed during readiness."
    return warning
