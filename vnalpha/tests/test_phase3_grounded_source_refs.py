from __future__ import annotations

import json

from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.groundedness import (
    GroundednessValidator,
    available_source_refs,
)
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan, ToolPlanStep
from vnalpha.assistant.response_parser import parse_synthesis_response
from vnalpha.assistant.synthesizer import AnswerSynthesizer

_ARTIFACT_REF = "candidate_score:FPT:2026-07-10"


def _plan() -> AssistantPlan:
    return AssistantPlan(
        intent="deep_analyze_symbol",
        steps=[
            ToolPlanStep(
                step_id="step_1",
                tool_name="analysis.deep_symbol",
                arguments={"symbol": "FPT", "date": "2026-07-10"},
                purpose="Review persisted FPT research evidence",
                required_permission="READ_SCORE",
            )
        ],
    )


def _tool_outputs() -> dict:
    return {
        "step_1": {
            "data": {
                "symbol": "FPT",
                "as_of_date": "2026-07-10",
                "candidate": {
                    "score": 0.75,
                    "candidate_class": "WATCH_CANDIDATE",
                },
                "feature_context": {"close": 100.0},
                "levels": {"support_20d": 95.0},
                "freshness": {"price_bar_date": "2026-07-10"},
                "lineage": {"source": "persisted warehouse"},
                "artifact_refs": [_ARTIFACT_REF],
                "missing_data": [],
                "caveats": ["Research-only persisted context."],
            },
            "summary": "Persisted deep-symbol evidence.",
            "warnings": [],
        }
    }


def _model_response(*, refs: list[str], claim_refs: dict | None = None) -> str:
    payload = {
        "summary": "Persisted research context is available.",
        "basis": "The deterministic deep-symbol payload supports this summary.",
        "risks_caveats": "Research-only context; freshness remains relevant.",
        "tool_trace_summary": "analysis.deep_symbol completed.",
        "missing_data": [],
        "grounded_source_refs": refs,
        "research_metadata": {},
    }
    if claim_refs is not None:
        payload["claim_source_refs"] = claim_refs
    return json.dumps(payload)


def test_missing_model_refs_trigger_bounded_deterministic_fallback() -> None:
    # Given: a valid research payload and a model answer that omits every source ref.
    plan = _plan()
    tool_outputs = _tool_outputs()
    synthesizer = AnswerSynthesizer(
        FakeLLMClient(responses=[(_model_response(refs=[]), {})])
    )

    # When: groundedness validation evaluates the model-generated answer.
    answer = synthesizer.synthesize("Review FPT", plan, tool_outputs)

    # Then: the model answer is rejected and fallback uses only bounded refs.
    assert synthesizer.last_fallback_used is True
    assert answer.research_metadata["fallback_used"] is True
    assert _ARTIFACT_REF in answer.grounded_source_refs
    assert set(answer.grounded_source_refs) <= set(
        available_source_refs(plan, tool_outputs)
    )


def test_parser_preserves_optional_claim_source_mapping() -> None:
    # Given: a model answer maps one stable claim ID to a bounded artifact ref.
    response = _model_response(
        refs=[_ARTIFACT_REF],
        claim_refs={"claim-fpt-score": [_ARTIFACT_REF]},
    )

    # When: the production synthesis parser reads the optional metadata.
    answer = parse_synthesis_response(response)

    # Then: the typed answer and serialized envelope retain the claim mapping.
    assert answer.claim_source_refs == {"claim-fpt-score": [_ARTIFACT_REF]}
    assert answer.to_dict()["claim_source_refs"] == {"claim-fpt-score": [_ARTIFACT_REF]}


def test_parser_defaults_missing_claim_source_mapping_to_empty() -> None:
    # Given/When: a backward-compatible answer omits claim-level metadata.
    answer = parse_synthesis_response(_model_response(refs=[_ARTIFACT_REF]))

    # Then: callers receive an empty mapping rather than a schema failure.
    assert answer.claim_source_refs == {}


def test_groundedness_rejects_unsupported_claim_source_ref() -> None:
    # Given: aggregate refs are valid but one claim points outside the bounded vocabulary.
    answer = AssistantAnswer(
        summary="Persisted research context is available.",
        basis="Deterministic evidence.",
        risks_caveats="Research-only context.",
        tool_trace_summary="analysis.deep_symbol completed.",
        grounded_source_refs=[_ARTIFACT_REF],
        claim_source_refs={"claim-fpt-score": ["artifact:not-present"]},
    )

    # When: final answer groundedness is validated.
    result = GroundednessValidator().validate(answer, _plan(), _tool_outputs())

    # Then: claim-level references are subject to the same bounded-ref policy.
    assert result.status == "FAIL"
    assert result.unsupported_source_refs == ("artifact:not-present",)


def test_groundedness_accepts_bounded_claim_source_ref() -> None:
    # Given: aggregate and claim-level references both use confirmed tool vocabulary.
    answer = AssistantAnswer(
        summary="Persisted research context is available.",
        basis="Deterministic evidence.",
        risks_caveats="Research-only context.",
        tool_trace_summary="analysis.deep_symbol completed.",
        grounded_source_refs=[_ARTIFACT_REF],
        claim_source_refs={"claim-fpt-score": [_ARTIFACT_REF]},
    )

    # When: final answer groundedness is validated.
    result = GroundednessValidator().validate(answer, _plan(), _tool_outputs())

    # Then: optional claim mapping preserves a PASS result.
    assert result.status == "PASS"
    assert result.unsupported_source_refs == ()
