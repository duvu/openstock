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
            if step.tool_name == "sandbox.run_research_code" and "job_id" in step.arguments:
                lines.append(
                    "  "
                    + f"{i}. sandbox.run_research_code(purpose={step.arguments.get('purpose')!r})"
                )
                lines.extend(
                    [
                        f"     job_id: {step.arguments.get('job_id')}",
                        f"     code summary: {step.arguments.get('code_summary')}",
                        f"     code digest: {step.arguments.get('code_digest')}",
                        "     input datasets: "
                        + (
                            ", ".join(step.arguments.get("input_references", []))
                            or "(none)"
                        ),
                        "     resource limits: "
                        + (
                            f"{step.arguments.get('resource_limits', {}).get('cpu_millis')} millicpu, "
                            f"{step.arguments.get('resource_limits', {}).get('memory_mb')} MB, "
                            f"{step.arguments.get('resource_limits', {}).get('timeout_seconds')}s"
                        ),
                        f"     image digest: {step.arguments.get('image_digest')}",
                    ]
                )
                continue
            args_repr = ", ".join(f"{k}={v!r}" for k, v in step.arguments.items())
            lines.append(f"  {i}. {step.tool_name}({args_repr})")
    lines.append("")
    lines.append("Approve? Press 'a' to approve, Esc to cancel.")
    return "\n".join(lines)
