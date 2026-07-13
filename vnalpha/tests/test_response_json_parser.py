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
