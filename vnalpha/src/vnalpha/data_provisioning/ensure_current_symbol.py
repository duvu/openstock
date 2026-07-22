"""Unified current-symbol provisioning operation shared by chat and commands.

``ensure_current_symbol_ready`` is the single typed application operation that
issue #163 requires. Both the natural-language planner (via the
``data.ensure_current_symbol`` tool) and slash-command handlers delegate to it,
so provisioning is:

* explicit — represented as a real plan/tool step rather than a hidden
  executor-only pre-step;
* traceable — one correlation ID spans provisioning and downstream analysis;
* idempotent — fresh persisted data is reused unless an explicit refresh is
  requested, in which case bounded incremental work runs.

It delegates to the existing fail-closed ``DeepAnalysisReadinessService`` and the
``data_availability`` engine, preserving typed provider failures, quarantine,
quality, lineage and writer-lock behaviour. It never grants the assistant raw
SQL, filesystem, shell, network or trading capability.
"""

from __future__ import annotations

import duckdb

from vnalpha.core.symbols import (
    INVALID_SYMBOL_FORMAT,
    SymbolFormatError,
    validate_ticker,
)
from vnalpha.data_availability.deep_readiness_models import (
    ContextRequirement,
)
from vnalpha.data_availability.deep_readiness_service import (
    DeepAnalysisReadinessService,
)
from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
from vnalpha.data_availability.models import EnsureDataResult
from vnalpha.data_provisioning.current_symbol_models import (
    CurrentSymbolReadyResult,
    ProvisioningAction,
    ProvisioningOutcome,
)
from vnalpha.data_provisioning.current_symbol_readiness import (
    build_ready_result,
    readiness_request,
)
from vnalpha.data_provisioning.data_only_symbol import provision_data_only_symbol
from vnalpha.observability.audit import log_audit
from vnalpha.observability.context import get_correlation_id, set_correlation_id


def ensure_current_symbol_ready(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    requested_date: str | None = None,
    *,
    refresh: bool = False,
    data_only: bool = False,
    market_regime_requirement: ContextRequirement = ContextRequirement.NOT_REQUESTED,
    sector_strength_requirement: ContextRequirement = ContextRequirement.NOT_REQUESTED,
    correlation_id: str | None = None,
) -> CurrentSymbolReadyResult:
    """Provision and validate the minimum current-symbol analysis inputs.

    Args:
        conn: Live warehouse connection.
        symbol: Primary Vietnamese equity symbol for this turn.
        requested_date: Optional explicit as-of date; ``None`` means latest.
        refresh: When ``True`` perform bounded incremental provisioning even if
            persisted data already satisfies the freshness policy.
        market_regime_requirement / sector_strength_requirement: Optional context
            gates forwarded to deep-analysis readiness.
        correlation_id: Reuse an existing correlation chain when provided so the
            provisioning trace links to the calling turn.

    Returns:
        A typed :class:`CurrentSymbolReadyResult`.
    """

    active_correlation_id = _bind_correlation_id(correlation_id)

    # Reject a malformed ticker before acquiring the writer lock or touching the
    # warehouse (issue #315). The rejection is a typed INVALID_SYMBOL_FORMAT
    # failure kept distinct from the downstream SYMBOL_NOT_FOUND membership
    # failure, and no serialized value is ever passed on as a literal ticker.
    try:
        normalized_symbol = validate_ticker(symbol)
    except SymbolFormatError as exc:
        return _malformed_symbol_result(
            symbol, requested_date, refresh, active_correlation_id, str(exc)
        )

    def _ensure(
        ensure_conn: duckdb.DuckDBPyConnection,
        ensure_symbol: str,
        ensure_date: str | None,
    ) -> EnsureDataResult:
        return ensure_symbol_analysis_ready(
            ensure_conn,
            ensure_symbol,
            ensure_date,
            force_refresh=refresh,
        )

    log_audit(
        "CURRENT_SYMBOL_PROVISIONING_STARTED",
        f"Current-symbol provisioning started for {normalized_symbol}.",
        extra={
            "symbol": normalized_symbol,
            "requested_date": requested_date,
            "refresh": refresh,
            "data_only": data_only,
            "correlation_id": active_correlation_id,
        },
    )
    if data_only:
        result = provision_data_only_symbol(
            conn,
            normalized_symbol,
            requested_date,
            refresh=refresh,
            correlation_id=active_correlation_id,
        )
    else:
        service = DeepAnalysisReadinessService(ensure=_ensure)
        readiness = service.ensure_ready(
            readiness_request(
                conn,
                normalized_symbol,
                requested_date,
                market_regime_requirement,
                sector_strength_requirement,
            )
        )
        result = build_ready_result(
            normalized_symbol,
            requested_date,
            refresh,
            readiness,
            active_correlation_id,
        )
    log_audit(
        "CURRENT_SYMBOL_PROVISIONING_COMPLETED",
        f"Current-symbol provisioning {result.outcome.value} for {normalized_symbol}.",
        status="OK" if result.is_ready else "FAILED",
        level="INFO" if result.is_ready else "ERROR",
        extra={
            "symbol": normalized_symbol,
            "outcome": result.outcome.value,
            "correlation_id": active_correlation_id,
            "actions": [action.action for action in result.actions],
            "reused_fresh_data": result.reused_fresh_data,
            "refreshed": result.refreshed,
        },
    )
    return result


def _malformed_symbol_result(
    symbol: str,
    requested_date: str | None,
    refresh: bool,
    correlation_id: str,
    detail: str,
) -> CurrentSymbolReadyResult:
    """Build a typed FAILED result for a malformed ticker (INVALID_SYMBOL_FORMAT).

    Surfaced before any lock/warehouse work so the syntax failure never reaches
    provisioning and stays distinct from a SYMBOL_NOT_FOUND membership failure.
    """
    log_audit(
        "CURRENT_SYMBOL_PROVISIONING_COMPLETED",
        f"Current-symbol provisioning rejected malformed ticker {symbol!r}.",
        status="FAILED",
        level="ERROR",
        extra={
            "symbol": symbol,
            "outcome": ProvisioningOutcome.FAILED.value,
            "failure_category": INVALID_SYMBOL_FORMAT,
            "correlation_id": correlation_id,
        },
    )
    return CurrentSymbolReadyResult(
        symbol=symbol if isinstance(symbol, str) else str(symbol),
        outcome=ProvisioningOutcome.FAILED,
        correlation_id=correlation_id,
        requested_date=requested_date,
        resolved_date=requested_date or "unresolved",
        actions=(
            ProvisioningAction(
                action="validate_symbol",
                status="FAILED",
                symbol=symbol if isinstance(symbol, str) else None,
                failure_category=INVALID_SYMBOL_FORMAT,
                root_cause=detail,
            ),
        ),
        reused_fresh_data=False,
        refreshed=False,
        warnings=(),
        errors=(detail,),
    )


def _bind_correlation_id(correlation_id: str | None) -> str:
    if correlation_id:
        return set_correlation_id(parent=correlation_id)
    current = get_correlation_id()
    if current and current != "unset":
        return current
    return set_correlation_id()


__all__ = [
    "ensure_current_symbol_ready",
    "CurrentSymbolReadyResult",
    "ProvisioningAction",
    "ProvisioningOutcome",
]
