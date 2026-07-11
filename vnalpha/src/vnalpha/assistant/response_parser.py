"""
LLM response parsing utilities shared across assistant stages.

The parser remains backward compatible with the original answer envelope while
accepting optional grounded-source and research-metadata fields for deeper
research-intelligence workflows.
"""

from __future__ import annotations

import json

from vnalpha.assistant.errors import IntentClassificationError, SynthesisError
from vnalpha.assistant.models import SUPPORTED_INTENTS, AssistantAnswer, IntentResult


def strip_markdown_fence(text: str) -> str:
    """Remove one outer Markdown code fence from model output."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    first_newline = stripped.find("\n")
    if first_newline == -1:
        return stripped
    inner = stripped[first_newline + 1 :]
    closing_idx = inner.rfind("```")
    if closing_idx != -1:
        inner = inner[:closing_idx]
    return inner.strip()


def parse_intent_response(response_text: str, user_prompt: str = "") -> IntentResult:
    """Parse classifier JSON and normalize unknown intents to a safe refusal."""
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
    entities = data.get("entities", {})
    if not isinstance(entities, dict):
        entities = {}
    return IntentResult(
        intent=intent,
        confidence=float(data.get("confidence", 0.5)),
        entities=entities,
        needs_clarification=bool(data.get("needs_clarification", False)),
        clarification_question=data.get("clarification_question"),
        safety_flags=list(data.get("safety_flags", [])),
    )


def parse_synthesis_response(response_text: str) -> AssistantAnswer:
    """Parse the grounded answer envelope returned by the synthesizer."""
    cleaned = strip_markdown_fence(response_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SynthesisError(
            f"Invalid JSON from synthesizer: {response_text[:100]}"
        ) from exc
    if not isinstance(data, dict):
        raise SynthesisError("Synthesizer response must be a JSON object.")

    source_refs = data.get("grounded_source_refs", [])
    if not isinstance(source_refs, list):
        source_refs = []
    metadata = data.get("research_metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    missing_data = data.get("missing_data", [])
    if not isinstance(missing_data, list):
        missing_data = [str(missing_data)]

    return AssistantAnswer(
        summary=str(data.get("summary", "")),
        basis=str(data.get("basis", "")),
        risks_caveats=str(data.get("risks_caveats", "")),
        tool_trace_summary=str(data.get("tool_trace_summary", "")),
        missing_data=[str(item) for item in missing_data],
        raw_tool_outputs=data.get("raw_tool_outputs", {})
        if isinstance(data.get("raw_tool_outputs", {}), dict)
        else {},
        grounded_source_refs=[str(item) for item in source_refs],
        research_metadata=metadata,
    )
