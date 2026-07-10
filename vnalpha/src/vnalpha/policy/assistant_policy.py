"""Derived assistant and autonomous-plan tool eligibility."""

from __future__ import annotations

from typing import Final

from vnalpha.policy.tool_policy import TOOL_CAPABILITIES

ASSISTANT_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    capability.name
    for capability in TOOL_CAPABILITIES
    if capability.allowed_for_assistant
)

AUTONOMOUS_PLAN_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    capability.name
    for capability in TOOL_CAPABILITIES
    if capability.allowed_for_assistant and capability.allowed_for_autonomous_plan
)
