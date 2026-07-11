from __future__ import annotations

import json

import pytest

from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.intent import IntentClassifier
from vnalpha.assistant.models import SUPPORTED_INTENTS, IntentResult
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.assistant.tool_policy import assert_safe_tool, is_safe_tool
from vnalpha.policy.assistant_policy import AUTONOMOUS_PLAN_TOOL_NAMES


INTENT_TO_TOOL = {
    "deep_analyze_symbol": "analysis.deep_symbol",
    "review_market_regime": "market.get_regime",
    "review_sector_strength": "sector.get_strength",
    "summarize_watchlist_deep": "watchlist.summarize_deep",
    "generate_shortlist": "shortlist.generate",
    "generate_research_scenario": "scenario.generate_research_plan",
    "review_setup_evidence": "evidence.get_setup_history",
}


@pytest.mark.parametrize("intent,tool_name", INTENT_TO_TOOL.items())
def test_research_intent_is_supported_and_builds_one_safe_tool(
    intent: str, tool_name: str
) -> None:
    entities = {
        "symbol": "FPT",
        "date": "2026-07-01",
        "setup_type": "ACCUMULATION_BASE",
    }
    plan = PlanBuilder().build(IntentResult(intent, 0.95, entities))

    assert intent in SUPPORTED_INTENTS
    assert plan.intent == intent
    assert [step.tool_name for step in plan.steps] == [tool_name]
    assert tool_name in AUTONOMOUS_PLAN_TOOL_NAMES
    assert is_safe_tool(tool_name)
    assert_safe_tool(tool_name)
    assert plan.required_artifacts


@pytest.mark.parametrize("intent", tuple(INTENT_TO_TOOL))
def test_classifier_accepts_every_research_intent(intent: str) -> None:
    response = json.dumps(
        {
            "intent": intent,
            "confidence": 0.97,
            "entities": {"symbol": "FPT", "date": "2026-07-01"},
            "needs_clarification": False,
            "clarification_question": None,
            "safety_flags": [],
        }
    )
    classifier = IntentClassifier(FakeLLMClient(responses=[(response, {})]))

    result = classifier.classify("warehouse grounded research request")

    assert result.intent == intent
    assert classifier._client.call_options[0]["task_type"] == "intent_classification"


def test_shortlist_plan_is_bounded_and_research_only() -> None:
    plan = PlanBuilder().build(
        IntentResult(
            "generate_shortlist",
            0.9,
            {
                "date": "2026-07-01",
                "limit": 7,
                "setup_type": "ACCUMULATION_BASE",
                "sector": "Technology",
            },
        )
    )

    assert plan.steps[0].arguments == {
        "date": "2026-07-01",
        "limit": 7,
        "setup": "ACCUMULATION_BASE",
        "sector": "Technology",
    }
    assert "persisted warehouse data" in plan.assumptions[0].lower()


def test_scenario_plan_has_no_execution_tool() -> None:
    plan = PlanBuilder().build(
        IntentResult(
            "generate_research_scenario",
            0.9,
            {"symbol": "FPT", "date": "2026-07-01", "with_evidence": True},
        )
    )

    assert plan.steps[0].tool_name == "scenario.generate_research_plan"
    assert all(
        not step.tool_name.startswith(("broker", "order", "account", "filesystem"))
        for step in plan.steps
    )
