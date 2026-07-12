from __future__ import annotations

import pytest

from vnalpha.assistant.errors import PlanValidationError, ToolExecutionError
from vnalpha.assistant.models import AssistantPlan, ToolPlanStep
from vnalpha.assistant.tool_policy import (
    SAFE_TOOLS,
    assert_safe_tool,
    is_approval_required_plan,
    is_forbidden_tool,
    is_safe_plan,
    is_safe_tool,
    unsafe_tools_in_plan,
)

SAFE_TOOL_NAMES = frozenset(
    {
        "watchlist.scan",
        "watchlist.filter",
        "candidate.compare",
        "candidate.explain",
        "quality.get_status",
        "quality.get_many_status",
        "lineage.get_symbol_lineage",
        "history.list_sessions",
        "note.create",
        "market.get_regime",
        "sector.get_strength",
        "sector.get_symbol_alignment",
    }
)

REQUIRED_FORBIDDEN_PREFIXES = (
    "broker",
    "order",
    "allocation",
    "account",
    "trading",
    "margin",
    "transfer",
    "portfolio",
)

REQUIRED_FORBIDDEN_NAMES = frozenset(
    {
        "place_order",
        "cancel_order",
        "modify_order",
        "submit_order",
        "execute_order",
        "get_holdings",
        "rebalance",
        "rebalance_holdings",
        "allocate",
        "allocate_capital",
        "get_account",
        "get_account_balance",
        "transfer_funds",
        "withdraw",
        "deposit",
        "connect_broker",
        "disconnect_broker",
        "authenticate_broker",
        "auto_execute",
        "schedule_trade",
        "automated_execution",
    }
)


def _step(tool_name: str) -> ToolPlanStep:
    return ToolPlanStep(
        step_id="step_1",
        tool_name=tool_name,
        arguments={},
        purpose="test",
        required_permission="READ_WATCHLIST",
    )


@pytest.mark.parametrize("tool_name", sorted(SAFE_TOOL_NAMES))
def test_safe_tool_when_canonical_name(tool_name: str) -> None:
    # Given: one canonical assistant tool name
    # When: its policy classification is requested
    # Then: the name is safe and not forbidden
    assert tool_name in SAFE_TOOLS
    assert is_safe_tool(tool_name)
    assert not is_forbidden_tool(tool_name)


@pytest.mark.parametrize(
    "tool_name",
    ["unknown.tool", "network.fetch", "broker.execute_trade", "python_exec"],
)
def test_unsafe_tool_when_unknown_or_forbidden_name(tool_name: str) -> None:
    # Given: a non-canonical or explicitly forbidden tool name
    # When: its policy classification is requested
    # Then: it cannot be used by the assistant
    assert not is_safe_tool(tool_name)


@pytest.mark.parametrize(
    "tool_name",
    ["network.fetch", "broker.execute_trade", "python_exec"],
)
def test_forbidden_tool_when_prefix_or_underscore_name(tool_name: str) -> None:
    # Given: a forbidden dotted-prefix or underscore-style tool name
    # When: forbidden-name classification is requested
    # Then: the policy flags it directly
    assert is_forbidden_tool(tool_name)


@pytest.mark.parametrize(
    "tool_name",
    [
        f"{prefix}{separator}action"
        for prefix in REQUIRED_FORBIDDEN_PREFIXES
        for separator in (".", "_")
    ],
)
def test_forbidden_tool_when_required_prefix_has_dotted_or_underscore_variant(
    tool_name: str,
) -> None:
    # Given: a hard-deny prefix in a dotted or underscore tool name
    # When: forbidden-name classification is requested
    # Then: the policy rejects every required variant
    assert is_forbidden_tool(tool_name)


@pytest.mark.parametrize("tool_name", sorted(REQUIRED_FORBIDDEN_NAMES))
def test_forbidden_tool_when_required_explicit_name(tool_name: str) -> None:
    # Given: an explicit hard-deny tool name from the OpenSpec design
    # When: forbidden-name classification is requested
    # Then: the policy rejects the name
    assert is_forbidden_tool(tool_name)


def test_assert_safe_tool_when_unknown_tool() -> None:
    # Given: an unknown assistant tool
    # When: execution safety is asserted
    # Then: a typed execution error prevents use
    with pytest.raises(ToolExecutionError, match="not allowed"):
        assert_safe_tool("unknown.tool")


def test_unsafe_plan_when_empty_plan() -> None:
    # Given: an empty non-refusal plan
    # When: plan safety is evaluated
    # Then: the plan is unsafe because it cannot execute a canonical tool
    plan = AssistantPlan(intent="scan_candidates", steps=[])
    assert not is_safe_plan(plan)
    assert unsafe_tools_in_plan(plan) == ()


def test_unsafe_plan_when_unknown_tool() -> None:
    # Given: a plan containing an unknown tool
    # When: plan safety is evaluated
    # Then: the unsafe tool is reported and the plan is rejected
    plan = AssistantPlan(intent="scan_candidates", steps=[_step("unknown.tool")])
    assert not is_safe_plan(plan)
    assert unsafe_tools_in_plan(plan) == ("unknown.tool",)
    with pytest.raises(PlanValidationError, match="not allowed"):
        assert_safe_tool("unknown.tool", error_type=PlanValidationError)


@pytest.mark.parametrize("tool_name", ["note.create"])
def test_safe_plan_when_assistant_eligible_write_tool(tool_name: str) -> None:
    # Given: a plan using an assistant-eligible write tool
    # When: plan safety is evaluated
    # Then: the plan remains valid
    plan = AssistantPlan(intent="test", steps=[_step(tool_name)])
    assert is_safe_plan(plan)
    assert unsafe_tools_in_plan(plan) == ()


def test_unsafe_plan_when_manual_only_data_tool() -> None:
    # Given: a tool that is available only through an explicit manual path
    # When: assistant plan safety is evaluated
    # Then: data.fetch is rejected from autonomous execution
    plan = AssistantPlan(intent="test", steps=[_step("data.fetch")])
    assert not is_safe_plan(plan)
    assert unsafe_tools_in_plan(plan) == ("data.fetch",)


def test_approval_required_plan_when_only_sandbox_step() -> None:
    # Given: a plan with the single generated-code sandbox step
    plan = AssistantPlan(
        intent="sandbox_research_calculation",
        steps=[_step("sandbox.run_research_code")],
    )

    # When: approval-required plan classification is requested
    # Then: the plan remains unsafe for autonomous execution but can await approval
    assert not is_safe_plan(plan)
    assert is_approval_required_plan(plan)


@pytest.mark.parametrize(
    "steps",
    [
        [],
        [_step("sandbox.run_research_code"), _step("watchlist.scan")],
        [_step("sandbox.run_research_code"), _step("sandbox.run_research_code")],
    ],
)
def test_not_approval_required_plan_when_sandbox_step_is_not_exact(
    steps: list[ToolPlanStep],
) -> None:
    # Given: a plan that is empty or has more than one step
    plan = AssistantPlan(intent="sandbox_research_calculation", steps=steps)

    # When: approval-required plan classification is requested
    # Then: it cannot enter the approval-only sandbox path
    assert not is_approval_required_plan(plan)
