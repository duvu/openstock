"""Deterministic rendering for research-only scenario plan answers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from vnalpha.research_intelligence.scenario_policy import (
    RESEARCH_ONLY_DISCLAIMER,
    validate_research_only_language,
)


def render_research_scenario_answer(
    plan: Mapping[str, Any],
    *,
    tool_outputs: dict[str, Any],
) -> dict[str, Any]:
    """Render a validated scenario artifact without using generative text."""
    validate_research_only_language(plan)
    summary = "\n".join(
        [
            f"Research scenario plan for {plan['symbol']} as of {plan['as_of_date']}.",
            "Current setup:",
            _json_block(plan["current_setup"]),
            "Key levels:",
            _json_block(plan["key_levels"]),
            f"Confidence: {float(plan['confidence']):.2f}.",
        ]
    )
    basis = "\n".join(
        [
            "Confirmation conditions:",
            _bullets(plan["confirmation_conditions"]),
            "Invalidation conditions:",
            _bullets(plan["invalidation_conditions"]),
            "Scenario tree:",
            _json_block(plan["scenario_tree"]),
            "Research estimate:",
            _json_block(plan["risk_reward_estimate"]),
            "Checklist:",
            _bullets(plan["checklist"]),
            "Future confirmation: review a subsequent persisted evidence snapshot before updating this research context.",
        ]
    )
    risks_caveats = "\n".join(
        [
            "Caveats:",
            _bullets(plan["caveats"]),
            "",
            str(plan.get("research_only_language", RESEARCH_ONLY_DISCLAIMER)),
        ]
    )
    answer = {
        "summary": summary,
        "basis": basis,
        "risks_caveats": risks_caveats,
        "tool_trace_summary": (
            "Rendered from the persisted scenario plan, deep-analysis, level, and evidence references."
        ),
        "missing_data": [],
        "raw_tool_outputs": tool_outputs,
    }
    validate_research_only_language(answer)
    return answer


def _bullets(values: object) -> str:
    if not isinstance(values, list):
        return f"- {values}"
    return "\n".join(f"- {value}" for value in values)


def _json_block(value: object) -> str:
    return json.dumps(value, default=str, ensure_ascii=False, sort_keys=True)
