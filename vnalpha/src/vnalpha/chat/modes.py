"""ExecutionMode enum and plan-safety helpers for the vnalpha chat controller."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnalpha.assistant.models import AssistantPlan


# ---------------------------------------------------------------------------
# ExecutionMode
# ---------------------------------------------------------------------------


class ExecutionMode(str, Enum):
    """Controls how the chat controller handles a planned tool sequence."""

    AUTO_EXECUTE_SAFE_TOOLS = "auto"
    """Execute immediately when every plan step is canonically safe."""

    AUTO_EXECUTE_SAFE_READ_ONLY = "auto"
    """Deprecated compatibility alias for AUTO_EXECUTE_SAFE_TOOLS."""

    PLAN_THEN_APPROVE = "plan_then_approve"
    """Always preview the plan and wait for explicit user approval before executing."""

    PLAN_ONLY = "plan_only"
    """Preview the plan but never execute it under any circumstances."""


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
            args_repr = ", ".join(f"{k}={v!r}" for k, v in step.arguments.items())
            lines.append(f"  {i}. {step.tool_name}({args_repr})")
    lines.append("")
    lines.append("Approve? Press 'a' to approve, Esc to cancel.")
    return "\n".join(lines)
