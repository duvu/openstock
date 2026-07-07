"""Tests for Section 10 — Safety and tool allowlist (tasks 10.1–10.4)."""

from __future__ import annotations

from vnalpha.chat.modes import ExecutionMode
from vnalpha.chat.safety import (
    filter_safe_tools,
    is_tool_allowed_in_chat,
    requires_plan_approval,
    validate_tool_call,
)


class TestIsToolAllowedInChat:
    def test_research_tool_allowed(self):
        assert is_tool_allowed_in_chat("scan_market") is True

    def test_place_order_disallowed(self):
        assert is_tool_allowed_in_chat("place_order") is False

    def test_broker_prefix_disallowed(self):
        assert is_tool_allowed_in_chat("broker_buy") is False

    def test_account_prefix_disallowed(self):
        assert is_tool_allowed_in_chat("account_balance") is False

    def test_order_prefix_disallowed(self):
        assert is_tool_allowed_in_chat("order_status") is False

    def test_allocation_prefix_disallowed(self):
        assert is_tool_allowed_in_chat("allocation_target") is False

    def test_watchlist_scan_allowed(self):
        assert is_tool_allowed_in_chat("watchlist.scan") is True

    def test_quality_check_allowed(self):
        assert is_tool_allowed_in_chat("quality_check") is True

    def test_cancel_order_disallowed(self):
        assert is_tool_allowed_in_chat("cancel_order") is False

    def test_get_holdings_disallowed(self):
        assert is_tool_allowed_in_chat("get_holdings") is False

    def test_rebalance_disallowed(self):
        assert is_tool_allowed_in_chat("rebalance") is False

    def test_broker_dotted_prefix_disallowed(self):
        assert is_tool_allowed_in_chat("broker.place_order") is False

    def test_account_dotted_prefix_disallowed(self):
        assert is_tool_allowed_in_chat("account.get_balance") is False


class TestRequiresPlanApproval:
    def test_scan_market_does_not_require_approval(self):
        assert requires_plan_approval("scan_market") is False

    def test_execute_python_requires_approval(self):
        assert requires_plan_approval("execute_python") is True

    def test_web_fetch_requires_approval(self):
        assert requires_plan_approval("web_fetch") is True

    def test_write_file_requires_approval(self):
        assert requires_plan_approval("write_file") is True

    def test_mcp_call_requires_approval(self):
        assert requires_plan_approval("mcp_call") is True

    def test_quality_check_does_not_require_approval(self):
        assert requires_plan_approval("quality_check") is False


class TestValidateToolCall:
    def test_safe_tool_auto_mode_allowed(self):
        allowed, reason = validate_tool_call(
            "scan_market", ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY
        )
        assert allowed is True
        assert reason is None

    def test_place_order_auto_mode_blocked(self):
        allowed, reason = validate_tool_call(
            "place_order", ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY
        )
        assert allowed is False
        assert reason is not None
        assert "not available" in reason

    def test_place_order_plan_then_approve_also_blocked(self):
        allowed, reason = validate_tool_call(
            "place_order", ExecutionMode.PLAN_THEN_APPROVE
        )
        assert allowed is False
        assert reason is not None

    def test_requires_approval_tool_blocked_in_auto_mode(self):
        allowed, reason = validate_tool_call(
            "execute_python", ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY
        )
        assert allowed is False
        assert reason is not None
        assert "plan approval" in reason.lower() or "PLAN_THEN_APPROVE" in reason

    def test_requires_approval_tool_allowed_in_plan_then_approve_mode(self):
        allowed, reason = validate_tool_call(
            "execute_python", ExecutionMode.PLAN_THEN_APPROVE
        )
        assert allowed is True
        assert reason is None

    def test_requires_approval_tool_allowed_in_plan_only_mode(self):
        allowed, reason = validate_tool_call("execute_python", ExecutionMode.PLAN_ONLY)
        assert allowed is True
        assert reason is None

    def test_reason_contains_tool_name_for_disallowed(self):
        _, reason = validate_tool_call(
            "cancel_order", ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY
        )
        assert "cancel_order" in reason

    def test_reason_contains_tool_name_for_approval_required(self):
        _, reason = validate_tool_call(
            "web_fetch", ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY
        )
        assert "web_fetch" in reason


class TestFilterSafeTools:
    def test_filters_disallowed_tools(self):
        result = filter_safe_tools(["scan_market", "place_order", "quality_check"])
        assert result == ["scan_market", "quality_check"]

    def test_preserves_order(self):
        result = filter_safe_tools(
            ["quality_check", "watchlist.scan", "fundamentals.get"]
        )
        assert result == ["quality_check", "watchlist.scan", "fundamentals.get"]

    def test_all_disallowed_returns_empty(self):
        result = filter_safe_tools(["place_order", "cancel_order", "broker_buy"])
        assert result == []

    def test_all_allowed_returns_same(self):
        tools = ["scan_market", "quality_check", "watchlist.scan"]
        assert filter_safe_tools(tools) == tools

    def test_empty_input_returns_empty(self):
        assert filter_safe_tools([]) == []

    def test_prefix_match_filtered(self):
        result = filter_safe_tools(["scan_market", "account_balance", "order_list"])
        assert result == ["scan_market"]


class TestPermissionState:
    def test_research_tool_returns_allow(self):
        from vnalpha.chat.safety import PermissionState, get_permission_state

        state = get_permission_state(
            "scan_market", ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY
        )
        assert state == PermissionState.ALLOW

    def test_forbidden_tool_returns_hard_deny(self):
        from vnalpha.chat.safety import PermissionState, get_permission_state

        state = get_permission_state(
            "place_order", ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY
        )
        assert state == PermissionState.HARD_DENY

    def test_broker_prefix_returns_hard_deny(self):
        from vnalpha.chat.safety import PermissionState, get_permission_state

        state = get_permission_state("broker_buy", ExecutionMode.PLAN_THEN_APPROVE)
        assert state == PermissionState.HARD_DENY

    def test_prompt_text_cannot_override_hard_deny(self):
        from vnalpha.chat.safety import PermissionState, get_permission_state

        override_attempts = [
            "place_order",
            "broker.place_order",
            "execute_order",
            "run_shell",
            "disable_safety",
            "bypass_safety",
            "hide_trace",
            "run_sql",
        ]
        for tool_name in override_attempts:
            state = get_permission_state(tool_name, ExecutionMode.PLAN_THEN_APPROVE)
            assert state == PermissionState.HARD_DENY, (
                f"Expected HARD_DENY for '{tool_name}', got {state}"
            )

    def test_approval_tool_auto_mode_returns_deny(self):
        from vnalpha.chat.safety import PermissionState, get_permission_state

        state = get_permission_state(
            "execute_python", ExecutionMode.AUTO_EXECUTE_SAFE_READ_ONLY
        )
        assert state == PermissionState.DENY

    def test_approval_tool_plan_mode_returns_ask(self):
        from vnalpha.chat.safety import PermissionState, get_permission_state

        state = get_permission_state("execute_python", ExecutionMode.PLAN_THEN_APPROVE)
        assert state == PermissionState.ASK
