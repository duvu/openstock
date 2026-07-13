from __future__ import annotations

from vnalpha.assistant.models import AssistantAnswer, IntentResult
from vnalpha.assistant.response_json import (
    INTENT_ALIASES,
    InvalidSynthesisResponseError,
    parse_classifier_response,
    parse_json_response,
    parse_synthesis_response,
    strip_markdown_fence,
)


def parse_intent_response(response_text: str, user_prompt: str = "") -> IntentResult:
    return parse_classifier_response(response_text, user_prompt=user_prompt)


__all__ = [
    "parse_intent_response",
    "parse_synthesis_response",
    "parse_json_response",
    "strip_markdown_fence",
    "INTENT_ALIASES",
    "InvalidSynthesisResponseError",
    "AssistantAnswer",
]
