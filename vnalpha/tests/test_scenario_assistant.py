from __future__ import annotations


def test_assistant_plans_research_scenario_with_one_safe_tool() -> None:
    from vnalpha.assistant.intent import CLASSIFIER_SYSTEM_PROMPT
    from vnalpha.assistant.models import IntentResult
    from vnalpha.assistant.planner import PlanBuilder
    from vnalpha.assistant.synthesizer import SYNTHESIZER_SYSTEM_PROMPT

    plan = PlanBuilder().build(
        IntentResult(
            intent="generate_research_scenario",
            confidence=1.0,
            entities={"symbol": "FPT", "date": "2025-01-31"},
        )
    )

    assert "generate_research_scenario" in CLASSIFIER_SYSTEM_PROMPT
    assert [(step.tool_name, step.required_permission) for step in plan.steps] == [
        ("scenario.generate_research_plan", "READ_FEATURES")
    ]
    assert "scenario plan" in SYNTHESIZER_SYSTEM_PROMPT.lower()
