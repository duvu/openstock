from __future__ import annotations

import pytest

from vnalpha.assistant.intent import CLASSIFIER_SYSTEM_PROMPT
from vnalpha.assistant.models import SUPPORTED_INTENTS, IntentResult
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.assistant.tool_policy import is_safe_tool
from vnalpha.tools.setup import build_local_tool_registry
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations

_INTENT_TO_TOOL = {
    "create_indicator_experiment": "research.indicator.run",
    "create_feature": "research.feature.create",
    "validate_feature": "research.feature.validate",
    "test_hypothesis": "research.hypothesis.test",
    "scan_pattern": "research.pattern.scan",
    "run_offline_event_study": "research.event_study.run",
}


@pytest.mark.parametrize(("intent", "tool_name"), _INTENT_TO_TOOL.items())
def test_research_automation_intents_build_deterministic_safe_plans(
    intent: str, tool_name: str
) -> None:
    entities = {
        "description": "relative strength 20 sessions vs VNINDEX",
        "definition": "rs_20 = rs_20d_vs_vnindex",
        "feature": "rs_20",
        "hypothesis": "positive rs_20 has better 20-session return",
        "pattern": "accumulation base with volatility contraction and volume dry-up",
        "event_condition": "breakout after accumulation base",
        "universe": "VN30",
        "horizon": 10,
    }

    plan = PlanBuilder().build(
        IntentResult(intent=intent, confidence=0.95, entities=entities)
    )

    assert intent in SUPPORTED_INTENTS
    assert plan.steps[0].tool_name == tool_name
    assert is_safe_tool(tool_name)
    assert "research_artifact" in plan.required_artifacts
    preview = PlanBuilder().preview(plan).lower()
    assert "dataset" in preview
    assert "generated code" in preview
    assert "caveat" in preview


def test_classifier_prompt_declares_all_research_automation_intents() -> None:
    for intent in _INTENT_TO_TOOL:
        assert f"- {intent}:" in CLASSIFIER_SYSTEM_PROMPT


def test_research_automation_tools_are_registered() -> None:
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        names = set(build_local_tool_registry(conn).names())

    assert set(_INTENT_TO_TOOL.values()).issubset(names)


def test_live_execution_language_builds_refusal_plan() -> None:
    plan = PlanBuilder().build(
        IntentResult(
            intent="run_offline_event_study",
            confidence=0.99,
            entities={"event_condition": "deploy live trades through broker"},
        )
    )

    assert plan.is_refusal()
    assert "live" in (plan.refusal_reason or "").lower()
