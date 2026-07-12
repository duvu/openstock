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

INTENT_ALIASES = {
    "get_stock_info": "explain_symbol",
    "show_stock_info": "explain_symbol",
    "get_stock": "explain_symbol",
}


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


def _extract_json_from_text(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]

    return None


def _preview(text: str, max_chars: int = 240) -> str:
    normalized = text.strip().replace("\n", "\\n")
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[:max_chars]}…"


def parse_intent_response(response_text: str, user_prompt: str = "") -> IntentResult:
    """Parse classifier JSON and normalize unknown intents to a safe refusal."""
    clean = strip_markdown_fence(response_text)
    parse_attempts: list[str] = [clean]
    if clean != response_text:
        parse_attempts.append(response_text)
    extracted = _extract_json_from_text(response_text)
    if extracted is not None:
        parse_attempts.append(extracted)

    data: dict | None = None
    last_exc: json.JSONDecodeError | None = None
    for candidate in parse_attempts:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_exc = exc
            continue
        else:
            if not isinstance(parsed, dict):
                data = {}
            else:
                data = parsed
            break

    if data is None:
        raise IntentClassificationError(
            f"Invalid JSON from classifier: {_preview(response_text)}"
        ) from last_exc

    raw_intent = data.get("intent", "unsupported_or_unsafe")
    if not isinstance(raw_intent, str):
        raw_intent = "unsupported_or_unsafe"

    intent = raw_intent.strip().lower().replace("-", "_")
    if intent not in SUPPORTED_INTENTS:
        intent = INTENT_ALIASES.get(intent, "unsupported_or_unsafe")
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
    claim_source_refs: dict[str, list[str]] = {}
    raw_claim_source_refs = data.get("claim_source_refs", {})
    if isinstance(raw_claim_source_refs, dict):
        for claim_id, refs in raw_claim_source_refs.items():
            normalized_claim_id = str(claim_id).strip()
            if not normalized_claim_id or not isinstance(refs, list):
                continue
            claim_source_refs[normalized_claim_id] = list(
                dict.fromkeys(str(item) for item in refs if item)
            )
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
        claim_source_refs=claim_source_refs,
    )
