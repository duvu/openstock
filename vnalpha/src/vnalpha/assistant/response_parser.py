"""
LLM response parsing utilities — shared across all assistant stages.

All functions in this module are pure (no I/O, no side effects) so they are
trivially testable and can be reused by any component that receives raw LLM text.

Public API
----------
strip_markdown_fence(text)          Strip a single ```...``` wrapper from LLM output.
parse_intent_response(text, prompt) Parse a classifier JSON response → IntentResult.
parse_synthesis_response(text)      Parse a synthesizer JSON response → AssistantAnswer.
"""

from __future__ import annotations

import json

from vnalpha.assistant.errors import IntentClassificationError, SynthesisError
from vnalpha.assistant.models import SUPPORTED_INTENTS, AssistantAnswer, IntentResult

# ---------------------------------------------------------------------------
# Low-level text normalisation
# ---------------------------------------------------------------------------


def strip_markdown_fence(text: str) -> str:
    """Remove a single ```[lang]...``` wrapper that LLMs occasionally emit.

    Only the outermost fence is stripped; nested fences are left intact.
    Handles both ``\\`\\`\\`json`` and plain ``\\`\\`\\``` opening tags.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    # Find the end of the opening fence line (e.g. "```json\n" or "```\n")
    first_newline = stripped.find("\n")
    if first_newline == -1:
        # Entire string is just the opening tag — nothing to unwrap
        return stripped

    inner = stripped[first_newline + 1 :]

    # Strip closing fence if present
    closing_idx = inner.rfind("```")
    if closing_idx != -1:
        inner = inner[:closing_idx]

    return inner.strip()


# ---------------------------------------------------------------------------
# Stage-specific parsers
# ---------------------------------------------------------------------------


def parse_intent_response(response_text: str, user_prompt: str = "") -> IntentResult:
    """Parse the raw text from the classifier LLM call into an IntentResult.

    Raises IntentClassificationError on malformed JSON.
    Falls back to ``unsupported_or_unsafe`` for unknown intents.
    """
    clean = strip_markdown_fence(response_text)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as exc:
        raise IntentClassificationError(
            f"Invalid JSON from classifier: {response_text[:100]}"
        ) from exc

    intent = data.get("intent", "unsupported_or_unsafe")
    if intent not in SUPPORTED_INTENTS:
        intent = "unsupported_or_unsafe"

    return IntentResult(
        intent=intent,
        confidence=float(data.get("confidence", 0.5)),
        entities=data.get("entities", {}),
        needs_clarification=bool(data.get("needs_clarification", False)),
        clarification_question=data.get("clarification_question"),
        safety_flags=list(data.get("safety_flags", [])),
    )


def parse_synthesis_response(response_text: str) -> AssistantAnswer:
    """Parse the raw text from the synthesizer LLM call into an AssistantAnswer.

    Raises SynthesisError on malformed JSON.
    """
    cleaned = strip_markdown_fence(response_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SynthesisError(
            f"Invalid JSON from synthesizer: {response_text[:100]}"
        ) from exc

    return AssistantAnswer(
        summary=data.get("summary", ""),
        basis=data.get("basis", ""),
        risks_caveats=data.get("risks_caveats", ""),
        tool_trace_summary=data.get("tool_trace_summary", ""),
        missing_data=data.get("missing_data", []),
        raw_tool_outputs=data.get("raw_tool_outputs", {}),
    )
