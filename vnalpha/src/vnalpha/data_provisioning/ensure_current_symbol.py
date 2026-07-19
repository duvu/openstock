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

from dataclasses import dataclass, field
from enum import Enum

import duckdb

from vnalpha.data_availability.deep_readiness_models import (
    ContextRequirement,
    ReadinessResult,
)
from vnalpha.data_availability.deep_readiness_service import (
    DeepAnalysisReadinessService,
)
from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
from vnalpha.data_availability.models import EnsureDataResult
from vnalpha.observability.audit import log_audit
from vnalpha.observability.context import get_correlation_id, set_correlation_id

# Provisioning actions surfaced in the tool/audit trace. Mirrors the
# EnsureDataAction vocabulary but uses the stable, user-facing verbs named by
# issue #163 (sync_symbols, sync_ohlcv, sync_index, build_canonical,
# build_features, score_symbol).
_ACTION_LABELS: dict[str, str] = {
    "CACHE_HIT": "reuse_fresh",
    "SYMBOLS_SYNCED": "sync_symbols",
    "OHLCV_SYNCED": "sync_ohlcv",
    "CANONICAL_BUILT": "build_canonical",
    "BENCHMARK_SYNCED": "sync_index",
    "BENCHMARK_CANONICAL_BUILT": "build_index_canonical",
    "FEATURES_BUILT": "build_features",
    "SCORED": "score_symbol",
}
_MAX_REMEDIATION_ITEMS = 8
_MAX_REMEDIATION_ITEM_CHARS = 512
_MAX_REMEDIATION_TOTAL_CHARS = 2_048


class ProvisioningOutcome(str, Enum):
    """Truthful terminal state of a current-symbol provisioning turn."""

    READY = "READY"
    REUSED = "REUSED"
    REFRESHED = "REFRESHED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ProvisioningAction:
    """One provisioning action surfaced on the trace."""

    action: str
    status: str

    def to_dict(self) -> dict[str, str]:
        return {"action": self.action, "status": self.status}


@dataclass(frozen=True, slots=True)
class CurrentSymbolReadyResult:
    """Typed result of a bounded current-symbol provisioning turn."""

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

    def to_trace_dict(self) -> dict[str, object]:
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

    normalized_symbol = symbol.upper().strip()
    active_correlation_id = _bind_correlation_id(correlation_id)

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
        from vnalpha.data_provisioning.data_only_symbol import (
            provision_data_only_symbol,
        )

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
            _readiness_request(
                conn,
                normalized_symbol,
                requested_date,
                market_regime_requirement,
                sector_strength_requirement,
            )
        )
        result = _build_result(
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


def _bind_correlation_id(correlation_id: str | None) -> str:
    if correlation_id:
        return set_correlation_id(parent=correlation_id)
    current = get_correlation_id()
    if current and current != "unset":
        return current
    return set_correlation_id()


def _readiness_request(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    requested_date: str | None,
    market_regime_requirement: ContextRequirement,
    sector_strength_requirement: ContextRequirement,
):
    from vnalpha.data_availability.deep_readiness_models import (
        DeepAnalysisReadinessRequest,
    )

    return DeepAnalysisReadinessRequest(
        conn,
        symbol,
        requested_date,
        market_regime_requirement,
        sector_strength_requirement,
    )


def _build_result(
    symbol: str,
    requested_date: str | None,
    refresh: bool,
    readiness: ReadinessResult,
    correlation_id: str,
) -> CurrentSymbolReadyResult:
    actions = _actions_from_readiness(readiness)
    reused = any(action.action == "reuse_fresh" for action in actions)
    provisioned = any(action.action != "reuse_fresh" for action in actions)
    remediation = _remediation_from_readiness(readiness)

    if not readiness.is_ready:
        outcome = ProvisioningOutcome.FAILED
    elif refresh:
        outcome = ProvisioningOutcome.REFRESHED
    elif reused and not provisioned:
        outcome = ProvisioningOutcome.REUSED
    else:
        outcome = ProvisioningOutcome.READY

    # A ready-with-caveats readiness stays ready; its caveats flow through as
    # warnings on the result below rather than downgrading the outcome.
    return CurrentSymbolReadyResult(
        symbol=symbol,
        outcome=outcome,
        correlation_id=correlation_id,
        requested_date=requested_date,
        resolved_date=readiness.resolved_date,
        actions=actions,
        reused_fresh_data=reused,
        refreshed=refresh and readiness.is_ready,
        warnings=tuple(readiness.warnings),
        errors=tuple(readiness.errors),
        remediation=remediation,
        readiness=readiness,
    )


def _actions_from_readiness(
    readiness: ReadinessResult,
) -> tuple[ProvisioningAction, ...]:
    seen: list[ProvisioningAction] = []
    if readiness.action_outcomes:
        for outcome in readiness.action_outcomes:
            label = _ACTION_LABELS.get(
                outcome.action.value, outcome.action.value.lower()
            )
            action = ProvisioningAction(action=label, status=outcome.status.value)
            if action not in seen:
                seen.append(action)
        return tuple(seen)
    for raw_action in readiness.actions:
        label = _ACTION_LABELS.get(raw_action, raw_action.lower())
        action = ProvisioningAction(action=label, status="SUCCESS")
        if action not in seen:
            seen.append(action)
    return tuple(seen)


def _remediation_from_readiness(readiness: ReadinessResult) -> tuple[str, ...]:
    remediation: list[str] = []

    def append_bounded(value: str) -> bool:
        if len(value) > _MAX_REMEDIATION_ITEM_CHARS:
            return False
        if (
            sum(len(item) for item in remediation) + len(value)
            > _MAX_REMEDIATION_TOTAL_CHARS
        ):
            return False
        if value not in remediation:
            remediation.append(value)
        return True

    for artifact in readiness.artifacts:
        if len(remediation) >= _MAX_REMEDIATION_ITEMS:
            break
        artifact_has_command = False
        raw_steps = getattr(artifact, "remediation_steps", None)
        steps = raw_steps if isinstance(raw_steps, (list, tuple)) else ()
        for step in steps:
            raw_command = getattr(step, "command", None)
            command = raw_command.strip() if isinstance(raw_command, str) else ""
            if not command:
                continue
            artifact_has_command = append_bounded(command) or artifact_has_command
            if len(remediation) >= _MAX_REMEDIATION_ITEMS:
                break
        raw_fallback = getattr(artifact, "remediation", None)
        fallback = raw_fallback.strip() if isinstance(raw_fallback, str) else ""
        if not artifact_has_command and fallback:
            append_bounded(fallback)
    return tuple(remediation)


__all__ = [
    "ensure_current_symbol_ready",
    "CurrentSymbolReadyResult",
    "ProvisioningAction",
    "ProvisioningOutcome",
]
