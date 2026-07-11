"""Intent classifier for the natural-language research assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from vnalpha.assistant.errors import IntentClassificationError
from vnalpha.assistant.models import IntentResult
from vnalpha.assistant.response_parser import parse_intent_response
from vnalpha.model_routing.models import ModelProfile, ModelTaskType

_log = structlog.get_logger("assistant.intent")

if TYPE_CHECKING:
    from vnalpha.assistant.gateway import LLMGatewayClient

UNSAFE_KEYWORDS: frozenset[str] = frozenset(
    {
        "buy",
        "sell",
        "order",
        "place" + " order",
        "execute trade",
        "broker",
        "account",
        "port" + "folio",
        "invest",
        "purchase",
        "transaction",
        "short",
        "long position",
        "guaranteed",
        "will go up",
        "will go down",
        "hide trace",
        "bypass",
        "fabricate",
        "ignore safety",
        "disable safety",
    }
)


def _deterministic_precheck(prompt: str) -> str | None:
    lower = prompt.lower()
    for keyword in UNSAFE_KEYWORDS:
        if keyword in lower:
            return "TRADING_EXECUTION"
    return None


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
- fetch_data: download, sync, or update OHLCV data for one or more symbols from the data service
- unsupported_or_unsafe: trading execution, web search, code execution, broker, account/allocation management, or unsupported request

Rules:
- Any buy/sell/order/trade/broker/account/allocation request MUST be classified as unsupported_or_unsafe.
- Any web search, Python execution, or MCP tool request MUST be classified as unsupported_or_unsafe.
- Requests to download/sync/fetch/update data for a symbol MUST be classified as fetch_data.
- Respond ONLY with valid JSON matching: {"intent": "<name>", "confidence": 0.0-1.0, "entities": {}, "needs_clarification": false, "clarification_question": null, "safety_flags": []}
"""


def _build_classifier_messages(user_prompt: str) -> list[dict]:
    return [
        {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


class IntentClassifier:
    def __init__(self, llm_client: LLMGatewayClient):
        self._client = llm_client
        self.last_usage: dict | None = None

    def classify(self, user_prompt: str) -> IntentResult:
        """Classify intent with small-profile routing and one stronger JSON retry."""
        unsafe_category = _deterministic_precheck(user_prompt)
        if unsafe_category:
            self.last_usage = None
            return IntentResult(
                intent="unsupported_or_unsafe",
                confidence=1.0,
                entities={},
                safety_flags=[unsafe_category],
            )

        messages = _build_classifier_messages(user_prompt)
        try:
            response_text, usage = self._client.chat(
                messages,
                stage="classify",
                task_type=ModelTaskType.INTENT_CLASSIFICATION.value,
                route_metadata={"requires_deep_reasoning": False},
            )
        except Exception as exc:
            raise IntentClassificationError(f"LLM call failed: {exc}") from exc

        try:
            result = parse_intent_response(response_text, user_prompt)
        except IntentClassificationError:
            try:
                response_text, usage = self._client.chat(
                    messages,
                    stage="classify",
                    task_type=ModelTaskType.INTENT_CLASSIFICATION.value,
                    model_profile=ModelProfile.DEFAULT,
                    route_metadata={"requires_deep_reasoning": False},
                )
                result = parse_intent_response(response_text, user_prompt)
            except Exception as exc:
                if isinstance(exc, IntentClassificationError):
                    raise
                raise IntentClassificationError(
                    f"LLM classifier retry failed: {exc}"
                ) from exc

        self.last_usage = usage
        _log.info(
            "intent_classified",
            intent=result.intent,
            confidence=result.confidence,
            entities=result.entities,
            raw_response=response_text[:200],
        )
        return result
