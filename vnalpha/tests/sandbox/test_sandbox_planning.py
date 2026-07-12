from __future__ import annotations

from vnalpha.assistant.models import IntentResult
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.assistant.tool_policy import is_safe_plan


def test_sandbox_calculation_creates_an_approval_gated_plan_step() -> None:
    plan = PlanBuilder().build(
        IntentResult(
            intent="sandbox_research_calculation",
            confidence=1.0,
            entities={"purpose": "compare persisted returns"},
        )
    )

    assert [step.tool_name for step in plan.steps] == ["sandbox.run_research_code"]
    assert plan.steps[0].required_permission == "SANDBOX_APPROVAL"
    assert not is_safe_plan(plan)
