from __future__ import annotations

import json

from vnalpha.assistant.models import IntentResult
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.assistant.synthesizer import _build_synthesis_messages


def _deep_plan():
    return PlanBuilder().build(
        IntentResult(
            intent="deep_analyze_symbol",
            confidence=1.0,
            entities={"symbol": "FPT", "date": "2026-07-10"},
        )
    )


def _analysis_step(plan):
    return next(
        step for step in plan.steps if step.tool_name == "analysis.current_symbol"
    )


def _deep_payload(plan):
    step = _analysis_step(plan)
    artifact_ref = "candidate_score:FPT:2026-07-10"
    return {
        step.step_id: {
            "data": {
                "tool": "analysis.current_symbol",
                "available": True,
                "symbol": "FPT",
                "as_of_date": "2026-07-10",
                "candidate": {
                    "score": 0.75,
                    "candidate_class": "WATCH_CANDIDATE",
                    "setup_type": "MOMENTUM_CONTINUATION",
                },
                "feature_context": {"close": 100.0, "ma20": 98.0},
                "levels": {"support_20d": 95.0, "resistance_20d": 105.0},
                "freshness": {"price_bar_date": "2026-07-10"},
                "lineage": {"source": "persisted warehouse"},
                "artifact_refs": [artifact_ref],
                "missing_data": [],
                "caveats": ["Research-only persisted context."],
            },
            "summary": "Persisted deep research context.",
            "warnings": [],
        }
    }, artifact_ref


def _response(**overrides):
    payload = {
        "summary": "FPT has a persisted score of 0.75 for research review.",
        "basis": "Based on the deterministic deep-symbol payload.",
        "risks_caveats": "Research-only context; data freshness remains relevant.",
        "tool_trace_summary": "analysis.current_symbol completed.",
        "missing_data": [],
        "grounded_source_refs": [],
        "research_metadata": {},
    }
    payload.update(overrides)
    return json.dumps(payload), {}


def test_research_prompt_contains_template_and_bounded_source_refs():
    plan = _deep_plan()
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "analysis.current_symbol"
    tool_outputs, artifact_ref = _deep_payload(plan)

    messages = _build_synthesis_messages("Review FPT", plan, tool_outputs)
    context = json.loads(messages[1]["content"])

    assert "Required payload fields" in context["research_template"]
    assert artifact_ref in context["valid_grounded_source_refs"]
    assert (
        f"tool:analysis.current_symbol:{_analysis_step(plan).step_id}"
        in context["valid_grounded_source_refs"]
    )
