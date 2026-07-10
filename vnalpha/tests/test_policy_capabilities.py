"""Tests for the central tool capability policy."""

from __future__ import annotations

from importlib.util import find_spec

import duckdb

from vnalpha.assistant.tool_policy import SAFE_TOOLS
from vnalpha.tools.models import ToolPermission
from vnalpha.tools.setup import TOOL_PERMISSIONS, build_local_tool_registry


def test_central_policy_package_exists_when_capabilities_are_needed() -> None:
    # Given: the local tool registry requires a single policy source of truth
    # When: the policy package is discovered
    # Then: the central capability module is available
    assert find_spec("vnalpha.policy.tool_policy") is not None


def test_data_fetch_is_manual_but_not_assistant_auto_executable() -> None:
    # Given: data.fetch is registered for explicit local invocation
    # When: assistant auto-executable tools are derived
    # Then: data.fetch keeps WRITE_DATA registration but is excluded from SAFE_TOOLS
    assert TOOL_PERMISSIONS["data.fetch"] is ToolPermission.WRITE_DATA
    assert "data.fetch" not in SAFE_TOOLS


def test_every_registered_tool_has_central_capability_metadata() -> None:
    # Given: every local tool has a declared permission
    # When: capability metadata is queried
    # Then: central policy defines the same complete set of tool names
    from vnalpha.policy.tool_policy import TOOL_CAPABILITIES_BY_NAME

    assert set(TOOL_CAPABILITIES_BY_NAME) == set(TOOL_PERMISSIONS)


def test_data_fetch_capability_derives_manual_and_assistant_eligibility() -> None:
    # Given: the central capability entry for data.fetch
    # When: mutation and eligibility metadata are derived
    # Then: it is manual-only warehouse mutation, never autonomous assistant work
    from vnalpha.policy.assistant_policy import AUTONOMOUS_PLAN_TOOL_NAMES
    from vnalpha.policy.tool_policy import TOOL_CAPABILITIES_BY_NAME

    capability = TOOL_CAPABILITIES_BY_NAME["data.fetch"]

    assert capability.permission is ToolPermission.WRITE_DATA
    assert capability.mutates_warehouse
    assert capability.allowed_for_command
    assert not capability.allowed_for_assistant
    assert not capability.allowed_for_autonomous_plan
    assert "data.fetch" not in AUTONOMOUS_PLAN_TOOL_NAMES


def test_data_fetch_remains_in_explicit_local_tool_registry() -> None:
    # Given: an explicit manual local-tool invocation path
    # When: its registry is constructed
    # Then: data.fetch remains registered with the central WRITE_DATA permission
    conn = duckdb.connect(":memory:")
    try:
        spec = build_local_tool_registry(conn).get_spec("data.fetch")
    finally:
        conn.close()

    assert spec.permission is ToolPermission.WRITE_DATA
