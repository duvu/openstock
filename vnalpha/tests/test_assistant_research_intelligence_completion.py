from __future__ import annotations

import json

import pytest

from vnalpha.assistant.errors import SynthesisError, ToolExecutionError
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.models import IntentResult
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.assistant.synthesizer import AnswerSynthesizer, _build_synthesis_messages
from vnalpha.assistant.tool_policy import assert_safe_tool, is_safe_tool


def _deep_plan():
    return PlanBuilder().build(
        IntentResult(
            intent="deep_analyze_symbol",
            confidence=1.0,
            entities={"symbol": "FPT", "date": "2026-07-10"},
        )
    )


def _analysis_step(plan):
    return next(step for step in plan.steps if step.tool_name == "analysis.deep_symbol")


def _deep_payload(plan):
    step = _analysis_step(plan)
    artifact_ref = "candidate_score:FPT:2026-07-10"
    return {
        step.step_id: {
            "data": {
                "tool": "analysis.deep_symbol",
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
        "tool_trace_summary": "analysis.deep_symbol completed.",
        "missing_data": [],
        "grounded_source_refs": [],
        "research_metadata": {},
    }
    payload.update(overrides)
    return json.dumps(payload), {}


def test_research_prompt_contains_template_and_bounded_source_refs():
    plan = _deep_plan()
    tool_outputs, artifact_ref = _deep_payload(plan)

    messages = _build_synthesis_messages("Review FPT", plan, tool_outputs)
    context = json.loads(messages[1]["content"])

    assert "Required payload fields" in context["research_template"]
    assert artifact_ref in context["valid_grounded_source_refs"]
    assert (
        f"tool:analysis.deep_symbol:{_analysis_step(plan).step_id}"
        in context["valid_grounded_source_refs"]
    )


def test_grounded_research_answer_passes_and_records_validation_metadata():
    plan = _deep_plan()
    tool_outputs, artifact_ref = _deep_payload(plan)
    synth = AnswerSynthesizer(
        FakeLLMClient(responses=[_response(grounded_source_refs=[artifact_ref])])
    )

    answer = synth.synthesize("Review FPT", plan, tool_outputs)

    assert artifact_ref in answer.grounded_source_refs
    assert synth.last_groundedness is not None
    assert synth.last_groundedness.status == "PASS"
    assert synth.last_policy is not None
    assert synth.last_policy.status == "PASS"
    assert answer.research_metadata["fallback_used"] is False


def test_unsupported_claims_are_rewritten_with_deterministic_fallback():
    plan = _deep_plan()
    tool_outputs, _artifact_ref = _deep_payload(plan)
    response = _response(
        summary="FPT has an unsupported score of 9.99.",
        grounded_source_refs=["artifact:not-present"],
    )
    synth = AnswerSynthesizer(FakeLLMClient(responses=[response]))

    answer = synth.synthesize("Review FPT", plan, tool_outputs)

    assert synth.last_fallback_used is True
    assert answer.research_metadata["fallback_used"] is True
    assert "9.99" not in answer.summary
    assert synth.last_groundedness is not None
    assert synth.last_groundedness.status == "PASS"


def test_shortlist_without_research_disclaimer_is_rewritten():
    plan = PlanBuilder().build(
        IntentResult(
            intent="generate_shortlist",
            confidence=1.0,
            entities={"date": "2026-07-10", "top": 3},
        )
    )
    shortlist_step, market_step = plan.steps
    tool_outputs = {
        shortlist_step.step_id: {
            "data": {
                "shortlist": [{"symbol": "FPT", "shortlist_score": 0.8}],
                "methodology": {"version": "shortlist-v1"},
                "freshness": {"watchlist_date": "2026-07-10"},
                "caveats": ["Human review remains required."],
                "artifact_refs": ["daily_watchlist:2026-07-10"],
                "missing_data": [],
            },
            "warnings": [],
        },
        market_step.step_id: {
            "data": {
                "snapshot": {"regime": "NEUTRAL"},
                "freshness": {"as_of_date": "2026-07-10"},
                "lineage": {"source": "market_regime_snapshot"},
                "quality": "COMPLETE",
                "artifact_refs": ["market_regime_snapshot:2026-07-10"],
                "missing_data": [],
                "caveats": [],
            },
            "warnings": [],
        },
    }
    response = _response(
        summary="FPT is the top prioritized symbol.",
        risks_caveats="Human review remains required.",
    )
    synth = AnswerSynthesizer(FakeLLMClient(responses=[response]))

    answer = synth.synthesize("Build a shortlist", plan, tool_outputs)

    assert synth.last_fallback_used is True
    assert "Research shortlist" in answer.summary
    assert "Research-only" in answer.risks_caveats
    assert synth.last_policy is not None
    assert synth.last_policy.status == "PASS"


def test_missing_required_tool_output_fails_before_model_call():
    plan = _deep_plan()
    fake = FakeLLMClient(responses=[_response()])
    synth = AnswerSynthesizer(fake)

    with pytest.raises(SynthesisError, match="before synthesis"):
        synth.synthesize("Review FPT", plan, {})

    assert fake.calls == []


@pytest.mark.parametrize(
    ("intent", "entities", "expected_tool"),
    [
        (
            "deep_analyze_symbol",
            {"symbol": "FPT", "date": "2026-07-10"},
            "analysis.deep_symbol",
        ),
        ("review_market_regime", {"date": "2026-07-10"}, "market.get_regime"),
        ("review_sector_strength", {"date": "2026-07-10"}, "sector.get_strength"),
        (
            "summarize_watchlist_deep",
            {"date": "2026-07-10"},
            "watchlist.summarize_deep",
        ),
        ("generate_shortlist", {"date": "2026-07-10"}, "shortlist.generate"),
        (
            "generate_research_scenario",
            {"symbol": "FPT", "date": "2026-07-10"},
            "scenario.generate_research_plan",
        ),
        (
            "review_setup_evidence",
            {"setup_type": "MOMENTUM_CONTINUATION"},
            "evidence.get_setup_history",
        ),
    ],
)
def test_every_research_intent_has_deterministic_plan(
    intent: str,
    entities: dict,
    expected_tool: str,
):
    plan = PlanBuilder().build(
        IntentResult(intent=intent, confidence=1.0, entities=entities)
    )

    assert plan.is_refusal() is False
    assert expected_tool in {step.tool_name for step in plan.steps}


@pytest.mark.parametrize(
    "tool_name",
    [
        "analysis.deep_symbol",
        "market.get_regime",
        "sector.get_strength",
        "watchlist.summarize_deep",
        "shortlist.generate",
        "scenario.generate_research_plan",
        "evidence.get_setup_history",
    ],
)
def test_research_tools_use_central_safe_tool_policy(tool_name: str):
    assert is_safe_tool(tool_name)
    assert_safe_tool(tool_name)


def test_unsafe_execution_tool_remains_denied():
    assert is_safe_tool("data.fetch") is False
    with pytest.raises(ToolExecutionError, match="not allowed"):
        assert_safe_tool("data.fetch")
