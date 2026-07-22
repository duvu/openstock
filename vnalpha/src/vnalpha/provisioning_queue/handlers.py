from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, assert_never

import duckdb

from vnalpha.data_availability.artifact_readiness_models import ReadinessCapability
from vnalpha.data_provisioning.ensure_current_symbol import (
    CurrentSymbolReadyResult,
    ensure_current_symbol_ready,
)
from vnalpha.provisioning_queue.models import (
    EnsureCurrentSymbolGoal,
    GoalType,
    ProvisioningGoal,
    RefreshMode,
)


@dataclass(frozen=True, slots=True)
class HandlerResult:
    succeeded: bool
    detail: str


class ProvisioningGoalStage(Protocol):
    name: str
    requires_warehouse_write: bool

    def execute(
        self, connection: duckdb.DuckDBPyConnection | None
    ) -> HandlerResult: ...


@dataclass(frozen=True, slots=True)
class ProvisioningStage:
    name: str
    requires_warehouse_write: bool
    action: Callable[[duckdb.DuckDBPyConnection | None], HandlerResult]

    def execute(
        self, connection: duckdb.DuckDBPyConnection | None
    ) -> HandlerResult:
        return self.action(connection)


class ProvisioningGoalHandler(Protocol):
    """A statically registered implementation for one finite goal type."""

    goal_type: GoalType

    def stages(self, goal: ProvisioningGoal) -> tuple[ProvisioningGoalStage, ...]: ...


@dataclass(frozen=True, slots=True)
class CurrentSymbolGoalHandler:
    """Run the existing current-symbol application operation after re-planning."""

    goal_type: GoalType = GoalType.ENSURE_CURRENT_SYMBOL

    def stages(self, goal: ProvisioningGoal) -> tuple[ProvisioningGoalStage, ...]:
        match goal:
            case EnsureCurrentSymbolGoal() as current_goal:
                return (
                    ProvisioningStage(
                        name="current-symbol-admission",
                        requires_warehouse_write=False,
                        action=lambda _: _admit_current_symbol(current_goal),
                    ),
                    ProvisioningStage(
                        name="current-symbol-provision",
                        requires_warehouse_write=True,
                        action=lambda connection: _provision_current_symbol(
                            current_goal, connection
                        ),
                    ),
                )
            case unreachable:
                assert_never(unreachable)


class CurrentSymbolHandlerConfigurationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


def _result_from_current_symbol(
    goal: EnsureCurrentSymbolGoal, result: CurrentSymbolReadyResult
) -> HandlerResult:
    evidence = f"{result.outcome.value} {goal.symbol} {result.resolved_date}"
    if result.is_ready:
        return HandlerResult(succeeded=True, detail=evidence)
    detail = "; ".join(result.errors) or evidence
    return HandlerResult(succeeded=False, detail=detail)


def _admit_current_symbol(goal: EnsureCurrentSymbolGoal) -> HandlerResult:
    if goal.requested_enrichments:
        return HandlerResult(False, "UNSUPPORTED_ENRICHMENT_REQUEST")
    return HandlerResult(True, "CURRENT_SYMBOL_ADMITTED")


def _provision_current_symbol(
    goal: EnsureCurrentSymbolGoal, connection: duckdb.DuckDBPyConnection | None
) -> HandlerResult:
    if connection is None:
        raise CurrentSymbolHandlerConfigurationError(
            "current-symbol provisioning requires a writable warehouse"
        )
    return _result_from_current_symbol(
        goal,
        ensure_current_symbol_ready(
            connection,
            goal.symbol,
            goal.effective_date.isoformat(),
            refresh=goal.refresh_mode is RefreshMode.FORCE_REFRESH,
            data_only=goal.desired_capability is ReadinessCapability.PRICE_ANALYSIS,
        ),
    )


__all__ = [
    "CurrentSymbolGoalHandler",
    "HandlerResult",
    "ProvisioningGoalHandler",
    "ProvisioningGoalStage",
    "ProvisioningStage",
]
