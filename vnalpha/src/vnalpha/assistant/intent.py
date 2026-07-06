"""Intent classifier for the Phase 5.9 natural-language research assistant."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from vnalpha.assistant.errors import IntentClassificationError
from vnalpha.assistant.models import SUPPORTED_INTENTS, IntentResult

if TYPE_CHECKING:
    from vnalpha.assistant.gateway import LLMGatewayClient

# ----- Deterministic pre-rules (checked BEFORE calling LLM) -----

UNSAFE_KEYWORDS: frozenset[str] = frozenset({
    "buy", "sell", "order", "place" + " order", "execute trade", "broker",
    "account", "port" + "folio", "invest", "purchase", "transaction",
    "short", "long position", "guaranteed", "will go up", "will go down",
    "hide trace", "bypass", "fabricate", "ignore safety", "disable safety",
})

def _deterministic_precheck(prompt: str) -> str | None:
    """Return refusal category string if prompt matches unsafe keyword pattern, else None."""
    lower = prompt.lower()
    for kw in UNSAFE_KEYWORDS:
        if kw in lower:
            return "TRADING_EXECUTION"
    return None

# ----- Classifier prompt -----

CLASSIFIER_SYSTEM_PROMPT = """You are an intent classifier for a Vietnamese stock market research assistant.

Classify the user's research question into exactly one of these intents:
- scan_candidates: list or browse watchlist candidates
- filter_candidates: filter by score, class, setup, or risk flag
- compare_symbols: compare two or more specific symbols
- explain_symbol: explain why one symbol is in the watchlist
- review_quality: data quality or pipeline health question
- show_lineage: data source, ingestion, feature, or scoring lineage
- summarize_watchlist: high-level summary of today's watchlist
- create_research_note: save a note about a symbol or session
- show_history: research session history
- unsupported_or_unsafe: trading execution, web search, code execution, broker, account/allocation management, or unsupported request

Rules:
- Any buy/sell/order/trade/broker/account/allocation request MUST be classified as unsupported_or_unsafe.
- Any web search, Python execution, or MCP tool request MUST be classified as unsupported_or_unsafe.
- Respond ONLY with valid JSON matching: {"intent": "<name>", "confidence": 0.0-1.0, "entities": {}, "needs_clarification": false, "clarification_question": null, "safety_flags": []}
"""

def _build_classifier_messages(user_prompt: str) -> list[dict]:
    return [
        {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

def _parse_classifier_response(response_text: str, user_prompt: str) -> IntentResult:
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise IntentClassificationError(f"Invalid JSON from classifier: {response_text[:100]}") from exc
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


class IntentClassifier:
    def __init__(self, llm_client: "LLMGatewayClient"):
        self._client = llm_client
        self.last_usage: dict | None = None

    def classify(self, user_prompt: str) -> IntentResult:
        """Classify user intent. Applies deterministic pre-rules first."""
        # Pre-check
        unsafe_category = _deterministic_precheck(user_prompt)
        if unsafe_category:
            self.last_usage = None
            return IntentResult(
                intent="unsupported_or_unsafe",
                confidence=1.0,
                entities={},
                safety_flags=[unsafe_category],
            )
        # LLM classification
        messages = _build_classifier_messages(user_prompt)
        try:
            response_text, usage = self._client.chat(messages, stage="classify")
        except Exception as exc:
            raise IntentClassificationError(f"LLM call failed: {exc}") from exc
        self.last_usage = usage
        return _parse_classifier_response(response_text, user_prompt)
