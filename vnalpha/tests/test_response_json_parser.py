from __future__ import annotations

import pytest

from vnalpha.assistant.response_json import (
    InvalidSynthesisResponseError,
    parse_classifier_response,
    parse_json_response,
    parse_synthesis_response,
)


def test_parse_classifier_response_recovers_markdown_fence() -> None:
    parsed = parse_classifier_response(
        '```json\n{"intent":"scan_candidates","confidence":0.92,"entities":{}}\n```'
    )
    assert parsed.intent == "scan_candidates"
    assert parsed.confidence == 0.92


def test_parse_classifier_response_embedded_json() -> None:
    parsed = parse_classifier_response(
        'payload: {"intent":"explain_symbol","entities":{"symbol":"FPT"}}'
    )
    assert parsed.intent == "explain_symbol"
    assert parsed.entities == {"symbol": "FPT"}


def test_parse_json_response_recovers_embedded_object() -> None:
    payload = parse_json_response(
        'Here is result: {"intent":"explain_symbol","confidence":0.9}',
        context="classifier",
    )
    assert payload["intent"] == "explain_symbol"
    assert payload["confidence"] == 0.9


def test_parse_synthesis_response_invalid_json_raises_synthesis_error() -> None:
    with pytest.raises(InvalidSynthesisResponseError, match="Invalid JSON"):
        parse_synthesis_response("not valid json")


def test_symbol_recovered_for_symbol_intent_when_classifier_omits_it() -> None:
    # Classifier returns deep_analyze_symbol but drops the symbol; recover it
    # from the raw Vietnamese prompt so the plan is not empty.
    parsed = parse_classifier_response(
        '{"intent":"deep_analyze_symbol","entities":{}}',
        user_prompt="phan tich co phieu fpt",
    )
    assert parsed.intent == "deep_analyze_symbol"
    assert parsed.entities.get("symbols") == ["FPT"]


def test_symbol_recovery_does_not_override_classifier_symbol() -> None:
    parsed = parse_classifier_response(
        '{"intent":"deep_analyze_symbol","entities":{"symbol":"VNM"}}',
        user_prompt="phan tich fpt",
    )
    # An explicitly classified symbol is never overridden by recovery.
    assert parsed.entities.get("symbol") == "VNM"
    assert "symbols" not in parsed.entities


def test_symbol_recovery_skips_non_symbol_intents() -> None:
    parsed = parse_classifier_response(
        '{"intent":"scan_candidates","entities":{}}',
        user_prompt="top nganh ngan hang hom nay",
    )
    assert "symbols" not in parsed.entities


def test_symbol_recovery_prefers_ticker_cue() -> None:
    # A ticker cue ("co phieu <TICKER>") pins the symbol even when other
    # 3-letter connector words are present in the prompt.
    parsed = parse_classifier_response(
        '{"intent":"deep_analyze_symbol","entities":{}}',
        user_prompt="phan tich gia co phieu fpt",
    )
    assert parsed.entities.get("symbols") == ["FPT"]


def test_symbol_recovery_supports_uppercase_multi_symbol_compare() -> None:
    parsed = parse_classifier_response(
        '{"intent":"compare_symbols","entities":{}}',
        user_prompt="so sanh FPT va VNM",
    )
    assert parsed.entities.get("symbols") == ["FPT", "VNM"]


def test_symbol_recovery_ignores_lowercase_words_without_cue() -> None:
    # Lowercase 3-letter words with no ticker cue are not treated as symbols;
    # the request fails safe (clarification) rather than guessing wrong.
    parsed = parse_classifier_response(
        '{"intent":"deep_analyze_symbol","entities":{}}',
        user_prompt="top nganh ngan hang hom nay",
    )
    assert "symbols" not in parsed.entities
