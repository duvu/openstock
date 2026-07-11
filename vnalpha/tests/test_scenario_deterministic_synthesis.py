from __future__ import annotations

import json

from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.models import AssistantPlan
from vnalpha.assistant.synthesizer import AnswerSynthesizer
from vnalpha.research_intelligence.scenario_policy import RESEARCH_ONLY_DISCLAIMER


def _scenario_plan() -> dict[str, object]:
    return {
        "scenario_plan_id": "scenario-1",
        "symbol": "FPT",
        "as_of_date": "2025-01-31",
        "current_setup": {"trend": {"state": "UPTREND"}},
        "key_levels": [{"kind": "SUPPORT", "value": 115.0}],
        "confirmation_conditions": ["Review subsequent persisted evidence."],
        "invalidation_conditions": ["Reassess if persisted evidence changes."],
        "scenario_tree": {
            name: {
                "condition": "Persisted evidence changes.",
                "evidence_to_watch": ["Trend state"],
                "risk_context": "Evidence may be incomplete.",
                "caveat": "Requires future confirmation.",
            }
            for name in (
                "base_case",
                "confirmation_case",
                "failed_confirmation_case",
                "low_quality_drift_case",
            )
        },
        "risk_reward_estimate": {"context": "Rough level-based research context."},
        "checklist": ["Review the next persisted snapshot."],
        "confidence": 0.8,
        "caveats": ["Data remains subject to revision."],
        "research_only_language": RESEARCH_ONLY_DISCLAIMER,
        "artifact_references": {"deep_analysis": {"table": "setup_analysis"}},
        "correlation_id": "assistant-session-1",
    }


def test_scenario_synthesis_uses_deterministic_validated_plan_not_model_text() -> None:
    unsafe_model_response = json.dumps(
        {
            "summary": "Acquire FPT now.",
            "basis": "Model text.",
            "risks_caveats": "None.",
            "tool_trace_summary": "Model text.",
            "missing_data": [],
        }
    )
    client = FakeLLMClient(responses=[(unsafe_model_response, {})])

    answer = AnswerSynthesizer(client).synthesize(
        "Create a scenario plan.",
        AssistantPlan(intent="generate_research_scenario", steps=[]),
        {"scenario": {"data": _scenario_plan()}},
    )

    assert client.calls == []
    assert "Acquire FPT now." not in answer.summary
    assert "Current setup" in answer.summary
    assert "base_case" in answer.basis
    assert RESEARCH_ONLY_DISCLAIMER in answer.risks_caveats
