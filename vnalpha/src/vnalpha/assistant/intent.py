"""Intent classifier for the natural-language research assistant."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

from vnalpha.assistant.errors import IntentClassificationError
from vnalpha.assistant.models import IntentResult
from vnalpha.assistant.research_intelligence_intents import (
    INTENT_DESCRIPTIONS,
    INTENT_EXAMPLES,
)
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
        pattern = rf"(?<!\w){re.escape(keyword)}(?!\w)"
        if re.search(pattern, lower):
            return "TRADING_EXECUTION"
    return None


_BASE_INTENT_LINES = [
    "- scan_candidates: list or browse watchlist candidates",
    "- filter_candidates: filter by score, class, setup, or risk flag",
    "- compare_symbols: compare two or more specific symbols",
    "- explain_symbol: explain why one symbol is in the watchlist",
    "- review_quality: data quality or pipeline health question",
    "- review_symbol_sector_alignment: a symbol's persisted sector research context",
    "- show_lineage: data source, ingestion, feature, or scoring lineage",
    "- summarize_watchlist: short high-level summary of today's watchlist",
    "- create_research_note: save a note about a symbol or session",
    "- show_history: research session history",
    "- fetch_data: explicit request to download, sync, or update OHLCV data",
    "- sandbox_research_calculation: approval-gated offline research calculation requiring generated code",
    "- unsupported_or_unsafe: execution, unrestricted tools, or unsupported request",
]

INTENT_CLASSIFICATION_SCHEMA: dict[str, str] = {"type": "json_object"}

_RESEARCH_INTENT_LINES = [
    f"- {name}: {description}" for name, description in INTENT_DESCRIPTIONS.items()
]
_EXAMPLE_LINES = [
    f'- "{example}" -> {name}' for name, example in INTENT_EXAMPLES.items()
]
CONTEXT_INTENT_EXAMPLES: dict[str, str] = {
    "review_market_regime": INTENT_EXAMPLES["review_market_regime"],
    "review_sector_strength": INTENT_EXAMPLES["review_sector_strength"],
    "review_symbol_sector_alignment": "How does FPT align with its sector context?",
}

CLASSIFIER_SYSTEM_PROMPT = "\n".join(
    [
        "You are an intent classifier for a Vietnamese stock market research assistant.",
        "",
        "Classify the user's question into exactly one supported intent:",
        *_BASE_INTENT_LINES,
        *_RESEARCH_INTENT_LINES,
        "",
        "Rules:",
        "- Any buy/sell/order/trade/broker/account/allocation request is unsupported_or_unsafe.",
        "- Raw Python execution, MCP, raw SQL, or filesystem requests are unsupported_or_unsafe.",
        "- Offline research calculations requiring generated code map to sandbox_research_calculation.",
        "- Requests to download/sync/fetch/update data map to fetch_data.",
        "- Use deep_analyze_symbol only for a full multi-factor symbol review; use explain_symbol for a score explanation.",
        "- Use summarize_watchlist_deep for structure/sector/setup/risk synthesis; use summarize_watchlist for a short summary.",
        "- A research shortlist is not an execution or allocation list.",
        *_EXAMPLE_LINES,
        "- Respond only with JSON matching: "
        '{"intent":"<name>","confidence":0.0,"entities":{},'
        '"needs_clarification":false,"clarification_question":null,"safety_flags":[]}',
    ]
)


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
                response_schema=INTENT_CLASSIFICATION_SCHEMA,
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
                    response_schema=INTENT_CLASSIFICATION_SCHEMA,
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
