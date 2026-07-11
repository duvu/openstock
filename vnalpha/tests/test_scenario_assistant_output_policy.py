from __future__ import annotations

import pytest

from vnalpha.assistant.errors import SynthesisError
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.models import AssistantPlan
from vnalpha.assistant.synthesizer import AnswerSynthesizer
from vnalpha.research_intelligence.scenario_policy import RESEARCH_ONLY_DISCLAIMER


def test_scenario_synthesis_rejects_unsafe_persisted_plan_before_model_use() -> None:
    unsafe_plan = {
        "scenario_plan_id": "unsafe-plan",
        "current_setup": {"summary": "Acquire FPT now."},
        "research_only_language": RESEARCH_ONLY_DISCLAIMER,
    }
    client = FakeLLMClient()

    with pytest.raises(SynthesisError, match="Scenario rendering failed"):
        AnswerSynthesizer(client).synthesize(
            "Create a scenario plan.",
            AssistantPlan(intent="generate_research_scenario", steps=[]),
            {"scenario": {"data": unsafe_plan}},
        )

    assert client.calls == []
