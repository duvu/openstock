from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, assert_never

import duckdb

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


class ProvisioningGoalHandler(Protocol):
    """A statically registered implementation for one finite goal type."""

    goal_type: GoalType
    requires_warehouse_write: bool

    def execute(
        self, goal: ProvisioningGoal, connection: duckdb.DuckDBPyConnection | None
    ) -> HandlerResult: ...


@dataclass(frozen=True, slots=True)
class CurrentSymbolGoalHandler:
    """Run the existing current-symbol application operation after re-planning."""

    goal_type: GoalType = GoalType.ENSURE_CURRENT_SYMBOL
    requires_warehouse_write: bool = True

    def execute(
        self, goal: ProvisioningGoal, connection: duckdb.DuckDBPyConnection | None
    ) -> HandlerResult:
        match goal:
            case EnsureCurrentSymbolGoal() as current_goal:
                if connection is None:
                    raise CurrentSymbolHandlerConfigurationError(
                        "current-symbol provisioning requires a writable warehouse"
                    )
                return _result_from_current_symbol(
                    current_goal,
                    ensure_current_symbol_ready(
                        connection,
                        current_goal.symbol,
                        current_goal.effective_date.isoformat(),
                        refresh=current_goal.refresh_mode is RefreshMode.FORCE_REFRESH,
                        data_only=False,
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


__all__ = [
    "CurrentSymbolGoalHandler",
    "HandlerResult",
    "ProvisioningGoalHandler",
]
