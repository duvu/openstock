from __future__ import annotations

from vnalpha.assistant.response_json import (
    parse_classifier_response,
)


def test_parse_classifier_response_recovers_markdown_fence() -> None:
    parsed = parse_classifier_response(
        '```json\n{"intent":"scan_candidates","confidence":0.92,"entities":{}}\n```'
    )
    assert parsed.intent == "scan_candidates"
    assert parsed.confidence == 0.92
