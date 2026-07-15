"""Intent classifier for the natural-language research assistant."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import structlog

from vnalpha.assistant.errors import IntentClassificationError
from vnalpha.assistant.models import SUPPORTED_INTENTS, IntentResult
from vnalpha.assistant.research_intelligence_intents import (
    INTENT_DESCRIPTIONS,
    INTENT_EXAMPLES,
)
from vnalpha.assistant.response_json import parse_classifier_response
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
        "execute a trade",
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

_FILTER_PROPERTIES: dict[str, dict[str, Any]] = {
    "score": {"type": ["number", "null"]},
    "min_score": {"type": ["number", "null"]},
    "candidate_class": {"type": ["string", "null"]},
    "class": {"type": ["string", "null"]},
    "setup": {"type": ["string", "null"]},
    "setup_type": {"type": ["string", "null"]},
    "risk_flag": {"type": ["string", "null"]},
}
_ENTITY_PROPERTIES: dict[str, dict[str, Any]] = {
    "symbol": {"type": ["string", "null"]},
    "symbols": {"type": "array", "items": {"type": "string"}},
    "date": {"type": ["string", "null"]},
    "universe": {"type": ["string", "null"]},
    "filters": {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(_FILTER_PROPERTIES),
        "properties": _FILTER_PROPERTIES,
    },
    "top": {"type": ["integer", "null"]},
    "min_score": {"type": ["number", "null"]},
    "setup_type": {"type": ["string", "null"]},
    "horizon": {"type": ["integer", "null"]},
    "horizon_sessions": {"type": ["integer", "null"]},
    "note_text": {"type": ["string", "null"]},
    "tags": {"type": "array", "items": {"type": "string"}},
    "limit": {"type": ["integer", "null"]},
    "purpose": {"type": ["string", "null"]},
}

INTENT_CLASSIFICATION_SCHEMA: dict[str, Any] = {
    "title": "vnalpha_intent_classification",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "intent",
        "confidence",
        "entities",
        "needs_clarification",
        "clarification_question",
        "safety_flags",
    ],
    "properties": {
        "intent": {"type": "string", "enum": sorted(SUPPORTED_INTENTS)},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "entities": {
            "type": "object",
            "additionalProperties": False,
            "required": sorted(_ENTITY_PROPERTIES),
            "properties": _ENTITY_PROPERTIES,
        },
        "needs_clarification": {"type": "boolean"},
        "clarification_question": {"type": ["string", "null"]},
        "safety_flags": {"type": "array", "items": {"type": "string"}},
    },
}

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
        "- Respond only with JSON matching the supplied response schema.",
        "- Include every schema field. Use null, [], and an all-null filters object for unused entities.",
    ]
)

_SCHEMA_REPAIR_PROMPT = (
    "The previous response did not satisfy the required JSON contract. Return exactly "
    "one JSON object matching the supplied schema, with every required field present "
    "and no markdown or explanatory text."
)


def _build_classifier_messages(
    user_prompt: str,
    *,
    schema_repair: bool = False,
) -> list[dict]:
    messages = [
        {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    if schema_repair:
        messages.append({"role": "system", "content": _SCHEMA_REPAIR_PROMPT})
    return messages


class IntentClassifier:
    def __init__(self, llm_client: LLMGatewayClient):
        self._client = llm_client
        self.last_usage: dict | None = None
        self.last_raw_responses: list[dict[str, Any]] = []

    def classify(
        self, user_prompt: str, *, session_id: str | None = None
    ) -> IntentResult:
        """Classify intent and perform one explicit schema-repair retry if needed."""
        unsafe_category = _deterministic_precheck(user_prompt)
        if unsafe_category:
            self.last_usage = None
            self.last_raw_responses = []
            return IntentResult(
                intent="unsupported_or_unsafe",
                confidence=1.0,
                entities={},
                safety_flags=[unsafe_category],
            )

        self.last_raw_responses = []
        messages = _build_classifier_messages(user_prompt)
        route_metadata: dict[str, Any] = {
            "requires_deep_reasoning": False,
            "schema_repair_retry": False,
        }
        if session_id is not None:
            route_metadata["session_id"] = session_id
        try:
            response_text, usage = self._client.chat(
                messages,
                response_schema=INTENT_CLASSIFICATION_SCHEMA,
                stage="classify",
                task_type=ModelTaskType.INTENT_CLASSIFICATION.value,
                route_metadata=route_metadata,
            )
        except Exception as exc:
            self._capture_gateway_raw_responses()
            raise IntentClassificationError(f"LLM call failed: {exc}") from exc
        self._capture_gateway_raw_responses()

        try:
            result = parse_classifier_response(response_text, user_prompt)
        except IntentClassificationError:
            retry_metadata = {**route_metadata, "schema_repair_retry": True}
            try:
                response_text, usage = self._client.chat(
                    _build_classifier_messages(user_prompt, schema_repair=True),
                    response_schema=INTENT_CLASSIFICATION_SCHEMA,
                    stage="classify",
                    task_type=ModelTaskType.INTENT_CLASSIFICATION.value,
                    model_profile=ModelProfile.DEFAULT,
                    route_metadata=retry_metadata,
                )
                self._capture_gateway_raw_responses()
                result = parse_classifier_response(response_text, user_prompt)
            except IntentClassificationError as retry_exc:
                raise IntentClassificationError(
                    f"Invalid JSON from classifier after schema-repair retry: {retry_exc}"
                ) from retry_exc
            except Exception as exc:
                self._capture_gateway_raw_responses()
                raise IntentClassificationError(
                    f"LLM classifier schema-repair retry failed: {exc}"
                ) from exc

        self.last_usage = usage
        _log.info(
            "intent_classified",
            intent=result.intent,
            confidence=result.confidence,
            entities=result.entities,
            response_content_chars=len(response_text),
        )
        return result

    def _capture_gateway_raw_responses(self) -> None:
        self.last_raw_responses.extend(
            dict(response) for response in self._client.last_raw_responses
        )
