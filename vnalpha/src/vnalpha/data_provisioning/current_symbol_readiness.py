from __future__ import annotations

import duckdb

from vnalpha.data_availability.deep_readiness_models import (
    ContextRequirement,
    DeepAnalysisReadinessRequest,
    ReadinessResult,
)
from vnalpha.data_provisioning.current_symbol_models import (
    CurrentSymbolReadyResult,
    ProvisioningAction,
    ProvisioningOutcome,
)

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


def readiness_request(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    requested_date: str | None,
    market_regime_requirement: ContextRequirement,
    sector_strength_requirement: ContextRequirement,
) -> DeepAnalysisReadinessRequest:
    return DeepAnalysisReadinessRequest(
        conn,
        symbol,
        requested_date,
        market_regime_requirement,
        sector_strength_requirement,
    )


def build_ready_result(
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
            action = ProvisioningAction(
                action=_ACTION_LABELS.get(
                    outcome.action.value, outcome.action.value.lower()
                ),
                status=outcome.status.value,
                dataset=getattr(outcome, "dataset", None),
                symbol=getattr(outcome, "symbol", None),
                failure_category=getattr(outcome, "failure_category", None),
                root_cause=getattr(outcome, "root_cause", None),
            )
            if action not in seen:
                seen.append(action)
        return tuple(seen)
    for raw_action in readiness.actions:
        action = ProvisioningAction(
            action=_ACTION_LABELS.get(raw_action, raw_action.lower()), status="SUCCESS"
        )
        if action not in seen:
            seen.append(action)
    return tuple(seen)


def _remediation_from_readiness(readiness: ReadinessResult) -> tuple[str, ...]:
    remediation: list[str] = []
    for artifact in readiness.artifacts:
        if len(remediation) >= _MAX_REMEDIATION_ITEMS:
            break
        artifact_has_command = False
        raw_steps = getattr(artifact, "remediation_steps", None)
        steps = raw_steps if isinstance(raw_steps, (list, tuple)) else ()
        for step in steps:
            command = getattr(step, "command", None)
            if not isinstance(command, str) or not command.strip():
                continue
            artifact_has_command = (
                _append_remediation(remediation, command.strip())
                or artifact_has_command
            )
            if len(remediation) >= _MAX_REMEDIATION_ITEMS:
                break
        fallback = getattr(artifact, "remediation", None)
        if not artifact_has_command and isinstance(fallback, str) and fallback.strip():
            _append_remediation(remediation, fallback.strip())
    return tuple(remediation)


def _append_remediation(remediation: list[str], value: str) -> bool:
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
