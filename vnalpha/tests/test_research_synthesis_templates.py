from __future__ import annotations

from vnalpha.assistant.models import IntentResult
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.assistant.research_templates import (
    RESEARCH_INTELLIGENCE_INTENTS,
    STRICT_POLICY_INTENTS,
    get_research_template,
    research_template_prompt,
)


def test_every_research_intent_has_tool_aligned_template() -> None:
    entities = {
        "symbol": "FPT",
        "date": "2026-07-01",
        "setup_type": "ACCUMULATION_BASE",
    }
    for intent in RESEARCH_INTELLIGENCE_INTENTS:
        template = get_research_template(intent)
        assert template is not None
        prompt = research_template_prompt(intent)
        assert prompt is not None
        assert prompt["required_sections"]
        assert prompt["required_caveats"]
        plan = PlanBuilder().build(IntentResult(intent, 0.95, entities))
        assert set(template.required_tools).issubset(
            {step.tool_name for step in plan.steps}
        )


def test_shortlist_and_scenario_use_strict_policy_templates() -> None:
    assert STRICT_POLICY_INTENTS == {
        "generate_shortlist",
        "generate_research_scenario",
    }
    for intent in STRICT_POLICY_INTENTS:
        template = get_research_template(intent)
        assert template is not None
        assert template.require_research_marker
