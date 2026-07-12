"""Canonical tool safety policy for assistant plans and execution."""

from __future__ import annotations

from vnalpha.assistant.errors import AssistantError, ToolExecutionError
from vnalpha.assistant.models import AssistantPlan
from vnalpha.policy.assistant_policy import AUTONOMOUS_PLAN_TOOL_NAMES
from vnalpha.policy.safety_policy import FORBIDDEN_TOOL_NAMES, FORBIDDEN_TOOL_PREFIXES

SAFE_TOOLS = AUTONOMOUS_PLAN_TOOL_NAMES
APPROVAL_REQUIRED_TOOLS = frozenset({"sandbox.run_research_code"})


def is_forbidden_tool(tool_name: str) -> bool:
    """Return whether a tool is explicitly prohibited for the assistant."""
    return tool_name in FORBIDDEN_TOOL_NAMES or any(
        tool_name == prefix
        or tool_name.startswith(f"{prefix}.")
        or tool_name.startswith(f"{prefix}_")
        for prefix in FORBIDDEN_TOOL_PREFIXES
    )


def is_safe_tool(tool_name: str) -> bool:
    """Return whether a tool is explicitly approved for assistant use."""
    return tool_name in SAFE_TOOLS and not is_forbidden_tool(tool_name)


def is_assistant_plan_tool(tool_name: str) -> bool:
    """Return whether a tool may appear in an assistant plan at all."""
    return (
        is_safe_tool(tool_name) or tool_name in APPROVAL_REQUIRED_TOOLS
    ) and not is_forbidden_tool(tool_name)


def assert_safe_tool(
    tool_name: str, error_type: type[AssistantError] = ToolExecutionError
) -> None:
    """Raise the supplied assistant error when a tool is not canonical and safe."""
    if not is_safe_tool(tool_name):
        raise error_type(
            f"Tool '{tool_name}' is not allowed by the assistant tool policy."
        )


def assert_assistant_plan_tool(
    tool_name: str, error_type: type[AssistantError]
) -> None:
    """Reject planned tools outside the autonomous or approval-gated allowlists."""
    if not is_assistant_plan_tool(tool_name):
        raise error_type(
            f"Tool '{tool_name}' is not allowed by the assistant tool policy."
        )


def unsafe_tools_in_plan(plan: AssistantPlan) -> tuple[str, ...]:
    """Return every unsafe tool name in plan order."""
    return tuple(
        step.tool_name for step in plan.steps if not is_safe_tool(step.tool_name)
    )


def is_safe_plan(plan: AssistantPlan) -> bool:
    """Return whether every plan step uses a canonical safe tool."""
    return bool(plan.steps) and not unsafe_tools_in_plan(plan)
