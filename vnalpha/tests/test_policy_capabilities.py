"""Tests for the central tool capability policy."""

from __future__ import annotations

from importlib.util import find_spec


def test_central_policy_package_exists_when_capabilities_are_needed() -> None:
    # Given: the local tool registry requires a single policy source of truth
    # When: the policy package is discovered
    # Then: the central capability module is available
    assert find_spec("vnalpha.policy.tool_policy") is not None
