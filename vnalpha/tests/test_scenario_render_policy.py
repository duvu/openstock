from __future__ import annotations

import pytest

from vnalpha.commands.handlers.research_plan import handle_research_plan
from vnalpha.commands.parser import parse
from vnalpha.research_intelligence.scenario_policy import (
    RESEARCH_ONLY_DISCLAIMER,
    ScenarioLanguageValidationError,
)
from vnalpha.tools.models import ToolOutput


class _UnsafeScenarioTool:
    def call(self, *_args, **_kwargs) -> ToolOutput:
        return ToolOutput(
            data={
                "current_setup": {"summary": "Buy FPT now."},
                "key_levels": [],
                "confirmation_conditions": [],
                "invalidation_conditions": [],
                "scenario_tree": {},
                "risk_reward_estimate": None,
                "checklist": [],
                "caveats": [],
                "research_only_language": RESEARCH_ONLY_DISCLAIMER,
            },
            summary="unsafe fixture",
        )


def test_research_plan_rejects_execution_wording_before_rendering() -> None:
    with pytest.raises(ScenarioLanguageValidationError):
        handle_research_plan(
            parse("/research-plan FPT --date 2025-01-31"),
            conn=object(),
            tool_executor=_UnsafeScenarioTool(),
        )
