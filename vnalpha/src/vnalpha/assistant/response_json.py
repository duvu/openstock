from __future__ import annotations

import json
import re

from vnalpha.assistant.errors import (
    AssistantInputValidationError,
    IntentClassificationError,
    SynthesisError,
)
from vnalpha.assistant.models import SUPPORTED_INTENTS, AssistantAnswer, IntentResult
from vnalpha.core.symbols import SymbolFormatError, apply_canonical_symbols

INTENT_ALIASES = {
    "get_stock_info": "explain_symbol",
    "show_stock_info": "explain_symbol",
    "get_stock": "explain_symbol",
}

# Intents whose plan requires a concrete symbol. For these, if the classifier
# omitted the symbol, deterministically recover it from the raw prompt so an
# obvious ticker mention (e.g. "phan tich co phieu FPT") is not lost.
_SYMBOL_REQUIRING_INTENTS = frozenset(
    {
        "explain_symbol",
        "deep_analyze_symbol",
        "review_symbol_sector_alignment",
        "generate_research_scenario",
        "show_lineage",
        "compare_symbols",
    }
)

# Vietnamese/English words that match the 2-4 uppercase-letter shape but are
# never tickers; excluded from deterministic symbol recovery.
_SYMBOL_STOPWORDS = frozenset(
    {
        "CP",  # cổ phiếu marker handled separately by the planner
        "CK",  # chứng khoán marker
        "MA",
        "VN",
        "USD",
        "VND",
        "PE",
        "PB",
        "EPS",
        "ROE",
        "ROA",
        "AND",
        "THE",
        "FOR",
        "WHY",
        "HOW",
        # Common non-diacritic Vietnamese function words that share the 3-letter
        # ticker shape but are never symbols. Kept conservative: a recovered
        # symbol is still validated downstream by data.ensure_current_symbol, so
        # only unambiguous connectors are excluded here.
        "CUA",
        "VOI",
        "CHO",
        "NAO",
        "HAY",
        "XEM",
    }
)

# Words that explicitly signal "the following token is a ticker". When present,
# recovery trusts the token right after the cue even if it is not diacritic-safe.
_TICKER_CUES = frozenset(
    {"CP", "CK", "MA", "STOCK", "SYMBOL", "TICKER", "PHIEU", "MASP"}
)

# Whole alphabetic words only (bounded), so we never fragment a longer word
# like "research" into a spurious 3-letter "ticker".
_WORD_RE = re.compile(r"\b([A-Za-z]+)\b")


def _recover_symbols_from_prompt(prompt: str) -> list[str]:
    """Best-effort deterministic ticker recovery from the raw user prompt.

    Prefers the token immediately following a ticker cue ("co phieu", "cp",
    "ma", "stock", …). Only when no cue is present does it fall back to
    3-letter tokens that were typed in uppercase in the original prompt (a
    strong ticker signal). Conservative by design: it only supplements a
    missing classifier symbol, never overrides one, and any recovered symbol is
    still validated downstream.
    """
    raw_words = [match.group(1) for match in _WORD_RE.finditer(prompt)]
    upper_words = [word.upper() for word in raw_words]

    def _is_ticker_shaped(token: str) -> bool:
        return len(token) == 3 and token.isalpha() and token not in _SYMBOL_STOPWORDS

    cued: list[str] = []
    for index, token in enumerate(upper_words):
        if token in _TICKER_CUES and index + 1 < len(upper_words):
            nxt = upper_words[index + 1]
            if _is_ticker_shaped(nxt) and nxt not in cued:
                cued.append(nxt)
    if cued:
        return cued

    # No cue: only trust tokens the user typed in uppercase (e.g. "analyze HPG").
    candidates: list[str] = []
    for raw, token in zip(raw_words, upper_words, strict=True):
        if raw.isupper() and _is_ticker_shaped(token) and token not in candidates:
            candidates.append(token)
    return candidates


def strip_markdown_fence(text: str) -> str:
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


def parse_json_response(response_text: str, *, context: str) -> dict:
    clean = strip_markdown_fence(response_text)
    parse_attempts: list[str] = [response_text]
    if clean != response_text:
        parse_attempts.append(clean)
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
        if not isinstance(parsed, dict):
            continue
        data = parsed
        break

    if data is None:
        raise IntentClassificationError(
            f"Invalid JSON from {context}: {_preview(response_text)}"
        ) from last_exc

    return data


class InvalidSynthesisResponseError(SynthesisError):
    pass


def parse_synthesis_response(response_text: str) -> AssistantAnswer:
    try:
        data = parse_json_response(response_text, context="synthesizer")
    except IntentClassificationError as exc:
        raise InvalidSynthesisResponseError(
            f"Invalid JSON from synthesizer: {_preview(response_text)}"
        ) from exc

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


def parse_classifier_response(
    response_text: str, user_prompt: str = ""
) -> IntentResult:
    data = parse_json_response(response_text, context="classifier")

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

    # Canonicalize the symbol entities into a single representation before the
    # planner ever sees them (issue #315). This collapses JSON-valid-but-wrong
    # shapes ({"symbol": ["FPT"]}, {"symbol": "['FPT']"}, …) into
    # {"symbol": "FPT", "symbols": ["FPT"]} and rejects malformed shapes as a
    # typed INVALID_SYMBOL_FORMAT failure, so no arbitrary value is stringified
    # into a ticker literal downstream.
    if intent in _SYMBOL_REQUIRING_INTENTS:
        try:
            canonical = apply_canonical_symbols(entities)
        except SymbolFormatError as exc:
            raise AssistantInputValidationError(str(exc)) from exc

        # Deterministic symbol recovery runs ONLY when the classifier supplied
        # no canonical symbol, so an explicit mention (e.g. "phan tich co phieu
        # FPT") still executes without overriding a real classifier symbol.
        if canonical.primary_symbol is None and user_prompt:
            recovered = _recover_symbols_from_prompt(user_prompt)
            if recovered:
                entities["symbols"] = recovered
                apply_canonical_symbols(entities)

    confidence_raw = data.get("confidence", 0.5)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.5

    return IntentResult(
        intent=intent,
        confidence=confidence,
        entities=entities,
        needs_clarification=bool(data.get("needs_clarification", False)),
        clarification_question=data.get("clarification_question"),
        safety_flags=list(data.get("safety_flags", [])),
    )
