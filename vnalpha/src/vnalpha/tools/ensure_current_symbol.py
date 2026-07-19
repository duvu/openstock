"""Local tool wrapping the unified current-symbol provisioning operation.

This tool makes bounded data provisioning an explicit, traceable plan step for
both natural-language chat and slash commands (issue #163). It never fetches
arbitrary data: it delegates to the deterministic ``ensure_current_symbol_ready``
application operation, which owns provider access, quality, lineage and the
writer lock.
"""

from __future__ import annotations

import duckdb

from vnalpha.data_availability.deep_readiness_models import ContextRequirement
from vnalpha.data_provisioning.ensure_current_symbol import (
    ProvisioningOutcome,
    ensure_current_symbol_ready,
)
from vnalpha.tools.errors import (
    ActionableToolError,
    PublicToolFailure,
    ToolExecutionError,
)
from vnalpha.tools.models import ToolOutput


def ensure_current_symbol(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str | None = None,
    *,
    refresh: bool = False,
    data_only: bool = False,
    market_regime_requirement: ContextRequirement = ContextRequirement.NOT_REQUESTED,
    sector_strength_requirement: ContextRequirement = ContextRequirement.NOT_REQUESTED,
    correlation_id: str | None = None,
) -> ToolOutput:
    """Provision and validate the minimum current-symbol analysis inputs."""

    if not isinstance(symbol, str) or not symbol.strip():
        raise ToolExecutionError("data.ensure_current_symbol requires 'symbol'.")

    result = ensure_current_symbol_ready(
        conn,
        symbol,
        date,
        refresh=bool(refresh),
        data_only=data_only,
        market_regime_requirement=market_regime_requirement,
        sector_strength_requirement=sector_strength_requirement,
        correlation_id=correlation_id,
    )

    summary = _summary(result)
    if not result.is_ready:
        raise ActionableToolError(
            PublicToolFailure(
                reason=summary,
                remediation=result.remediation,
                correlation_id=result.correlation_id,
            )
        )
    warnings = list(result.warnings)
    return ToolOutput(
        data=result.to_trace_dict(),
        summary=summary,
        warnings=warnings,
    )


def _summary(result) -> str:
    actions = ", ".join(action.action for action in result.actions) or "no actions"
    if result.outcome is ProvisioningOutcome.REUSED:
        return f"{result.symbol}: reused fresh persisted data ({actions})."
    if result.outcome is ProvisioningOutcome.REFRESHED:
        return f"{result.symbol}: refreshed data ({actions})."
    if result.outcome is ProvisioningOutcome.READY:
        return f"{result.symbol}: provisioned data ({actions})."
    if result.errors:
        return result.errors[0]
    return f"{result.symbol}: provisioning did not complete."


__all__ = ["ensure_current_symbol"]
