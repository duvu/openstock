"""Tests for Section 10 — Safety and tool allowlist (tasks 10.1–10.4)."""

from __future__ import annotations

from vnalpha.assistant.tool_policy import SAFE_TOOLS
from vnalpha.chat.modes import ExecutionMode
from vnalpha.chat.safety import (
    filter_safe_tools,
    is_tool_allowed_in_chat,
    validate_tool_call,
)


class TestIsToolAllowedInChat:
    def test_each_canonical_safe_tool_is_allowed(self):
        for tool_name in SAFE_TOOLS:
            assert is_tool_allowed_in_chat(tool_name) is True

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

    def test_unknown_tool_is_disallowed(self):
        assert is_tool_allowed_in_chat("quality_check") is False

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


class TestValidateToolCall:
    def test_safe_tool_auto_mode_allowed(self):
        allowed, reason = validate_tool_call(
            "note.create", ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS
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

    def test_unknown_tool_is_blocked_in_auto_mode(self):
        allowed, reason = validate_tool_call(
            "write_file", ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS
        )
        assert allowed is False
        assert reason is not None
        assert "not available" in reason

    def test_unknown_tool_is_blocked_in_plan_then_approve_mode(self):
        allowed, reason = validate_tool_call(
            "write_file", ExecutionMode.PLAN_THEN_APPROVE
        )
        assert allowed is False
        assert reason is not None

    def test_unknown_tool_is_blocked_in_plan_only_mode(self):
        allowed, reason = validate_tool_call("write_file", ExecutionMode.PLAN_ONLY)
        assert allowed is False
        assert reason is not None

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
        result = filter_safe_tools(["note.create", "place_order", "quality_check"])
        assert result == ["note.create"]

    def test_preserves_order(self):
        result = filter_safe_tools(["data.fetch", "watchlist.scan", "quality_check"])
        assert result == ["watchlist.scan"]

    def test_all_disallowed_returns_empty(self):
        result = filter_safe_tools(["place_order", "cancel_order", "broker_buy"])
        assert result == []

    def test_all_allowed_returns_same(self):
        tools = ["note.create", "watchlist.scan"]
        assert filter_safe_tools(tools) == tools

    def test_empty_input_returns_empty(self):
        assert filter_safe_tools([]) == []

    def test_prefix_match_filtered(self):
        result = filter_safe_tools(["data.fetch", "account_balance", "order_list"])
        assert result == []


class TestPermissionState:
    def test_sandbox_tool_always_requires_approval(self):
        from vnalpha.chat.safety import PermissionState, get_permission_state

        assert (
            get_permission_state(
                "sandbox.run_research_code", ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS
            )
            == PermissionState.ASK
        )

    def test_manual_data_fetch_returns_deny(self):
        from vnalpha.chat.safety import PermissionState, get_permission_state

        state = get_permission_state(
            "data.fetch", ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS
        )
        assert state == PermissionState.DENY

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
            "shell_exec",
            "python_exec",
            "raw_sql",
            "file_write",
        ]
        for tool_name in override_attempts:
            state = get_permission_state(tool_name, ExecutionMode.PLAN_THEN_APPROVE)
            assert state == PermissionState.HARD_DENY, (
                f"Expected HARD_DENY for '{tool_name}', got {state}"
            )

    def test_unknown_tool_auto_mode_returns_deny(self):
        from vnalpha.chat.safety import PermissionState, get_permission_state

        state = get_permission_state(
            "write_file", ExecutionMode.AUTO_EXECUTE_SAFE_TOOLS
        )
        assert state == PermissionState.DENY

    def test_unknown_tool_plan_mode_returns_deny(self):
        from vnalpha.chat.safety import PermissionState, get_permission_state

        state = get_permission_state("write_file", ExecutionMode.PLAN_THEN_APPROVE)
        assert state == PermissionState.DENY
