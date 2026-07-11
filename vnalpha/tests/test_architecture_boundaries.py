from __future__ import annotations


def test_cli_shim_exposes_root_application() -> None:
    from vnalpha.cli import app

    assert app is not None


def test_data_fetch_is_manual_only() -> None:
    from vnalpha.policy.assistant_policy import (
        ASSISTANT_TOOL_NAMES,
        AUTONOMOUS_PLAN_TOOL_NAMES,
    )
    from vnalpha.tools.setup import TOOL_PERMISSIONS

    assert "data.fetch" in TOOL_PERMISSIONS
    assert "data.fetch" not in ASSISTANT_TOOL_NAMES
    assert "data.fetch" not in AUTONOMOUS_PLAN_TOOL_NAMES


def test_input_router_remains_a_direct_compatibility_alias() -> None:
    from vnalpha.tui.input_router import TuiInputRouter as compatibility_router
    from vnalpha.tui.routing.router import TuiInputRouter as routing_router

    assert compatibility_router is routing_router
