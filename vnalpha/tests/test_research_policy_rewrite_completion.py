from __future__ import annotations

import json

from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.models import IntentResult
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.assistant.synthesizer import AnswerSynthesizer


def test_execution_oriented_scenario_answer_is_rewritten_fail_closed():
    plan = PlanBuilder().build(
        IntentResult(
            intent="generate_research_scenario",
            confidence=1.0,
            entities={"symbol": "FPT", "date": "2026-07-10"},
        )
    )
    step = plan.steps[0]
    tool_outputs = {
        step.step_id: {
            "data": {
                "current_setup": {
                    "candidate_class": "WATCH_CANDIDATE",
                    "setup_type": "MOMENTUM_CONTINUATION",
                    "score": 0.75,
                },
                "key_levels": {
                    "latest_close": 100.0,
                    "support_20d": 95.0,
                    "resistance_20d": 105.0,
                },
                "scenarios": [
                    {"name": "confirmation", "conditions": ["close >= 105.0"]},
                    {"name": "neutral", "conditions": ["range persists"]},
                    {"name": "invalidation", "conditions": ["close < 95.0"]},
                ],
                "checklist": ["Review data freshness."],
                "artifact_refs": ["candidate_score:FPT:2026-07-10"],
                "freshness": {"as_of_date": "2026-07-10"},
                "lineage": {"source": "persisted warehouse"},
                "missing_data": [],
                "caveats": ["Research-only conditional context."],
            },
            "warnings": [],
        }
    }
    response = json.dumps(
        {
            "summary": "Buy now because the confirmation level is 105.0.",
            "basis": "The deterministic scenario payload.",
            "risks_caveats": "Research-only context.",
            "tool_trace_summary": "scenario.generate_research_plan completed.",
            "missing_data": [],
            "grounded_source_refs": ["candidate_score:FPT:2026-07-10"],
            "research_metadata": {},
        }
    )
    synth = AnswerSynthesizer(FakeLLMClient(responses=[(response, {})]))

    answer = synth.synthesize("Build a research scenario", plan, tool_outputs)

    assert synth.last_fallback_used is True
    assert "buy now" not in answer.summary.lower()
    assert "Conditional research scenario" in answer.summary
    assert "Research-only" in answer.risks_caveats
    assert synth.last_policy is not None
    assert synth.last_policy.status == "PASS"
