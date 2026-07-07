"""ExecutionMode enum and plan-safety helpers for the vnalpha chat controller."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnalpha.assistant.models import AssistantPlan

# ---------------------------------------------------------------------------
# Safe read-only tool allowlist
# ---------------------------------------------------------------------------

# Tools on this list are considered safe for AUTO_EXECUTE_SAFE_READ_ONLY mode.
# Broker, order, allocation, or account tools must NEVER appear here.
SAFE_READ_ONLY_TOOLS: frozenset[str] = frozenset(
    {
        "watchlist.scan",
        "quality.get_status",
        "quality.get_many_status",
        "fundamentals.get",
        "price.get",
        "price.get_range",
        "detail.get",
        "research.explain",
        "research.compare",
    }
)


# ---------------------------------------------------------------------------
# ExecutionMode
# ---------------------------------------------------------------------------


class ExecutionMode(str, Enum):
    """Controls how the chat controller handles a planned tool sequence."""

    AUTO_EXECUTE_SAFE_READ_ONLY = "auto"
    """Execute immediately when all plan steps are safe read-only tools."""

    PLAN_THEN_APPROVE = "plan_then_approve"
    """Always preview the plan and wait for explicit user approval before executing."""

    PLAN_ONLY = "plan_only"
    """Preview the plan but never execute it under any circumstances."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_safe_read_only_plan(plan: "AssistantPlan") -> bool:
    """Return True if *every* tool call in *plan* is in the safe allowlist.

    An empty plan (no steps) is considered safe.

    Parameters
    ----------
    plan:
        An :class:`~vnalpha.assistant.models.AssistantPlan` instance.

    Returns
    -------
    bool
        ``True`` when all step tool names are in :data:`SAFE_READ_ONLY_TOOLS`.
    """
    return all(step.tool_name in SAFE_READ_ONLY_TOOLS for step in plan.steps)


def format_plan_preview(plan: "AssistantPlan") -> str:
    """Format *plan* steps as a numbered list with an approval prompt.

    Example output::

        Plan:
          1. watchlist.scan(symbols=['VNM'])
          2. fundamentals.get(symbol='VNM')

        Approve? Press 'a' to approve, Esc to cancel.

    Parameters
    ----------
    plan:
        An :class:`~vnalpha.assistant.models.AssistantPlan` instance.

    Returns
    -------
    str
        Human-readable plan preview string.
    """
    if not plan.steps:
        lines = ["Plan:", "  (no steps)"]
    else:
        lines = ["Plan:"]
        for i, step in enumerate(plan.steps, start=1):
            args_repr = ", ".join(
                f"{k}={v!r}" for k, v in step.arguments.items()
            )
            lines.append(f"  {i}. {step.tool_name}({args_repr})")
    lines.append("")
    lines.append("Approve? Press 'a' to approve, Esc to cancel.")
    return "\n".join(lines)
