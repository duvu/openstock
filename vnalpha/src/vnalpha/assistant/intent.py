"""Intent classifier for the natural-language research assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from vnalpha.assistant.errors import IntentClassificationError
from vnalpha.assistant.models import IntentResult
from vnalpha.assistant.research_intelligence_intents import (
    classifier_examples,
    classifier_prompt_lines,
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
        if keyword in lower:
            return "TRADING_EXECUTION"
    return None


_CONTEXT_LINES = (
    "- review_market_regime: persisted market regime research context",
    "- review_sector_strength: persisted ranked sector strength research context",
    "- review_symbol_sector_alignment: a symbol's persisted sector research context",
)
_RESEARCH_LINES = classifier_prompt_lines()
_RESEARCH_EXAMPLES = classifier_examples()

CLASSIFIER_SYSTEM_PROMPT = "\n".join(
    [
        "You are an intent classifier for a Vietnamese stock market research assistant.",
        "",
        "Classify the user's research question into exactly one of these intents:",
        "- scan_candidates: list or browse watchlist candidates",
        "- filter_candidates: filter by score, class, setup, or risk flag",
        "- compare_symbols: compare two or more specific symbols",
        "- explain_symbol: explain one persisted candidate score",
        "- review_quality: data quality or pipeline health question",
        *_CONTEXT_LINES,
        "- show_lineage: data source, ingestion, feature, or scoring lineage",
        "- summarize_watchlist: short high-level watchlist summary",
        *_RESEARCH_LINES,
        "- create_research_note: save a note about a symbol or session",
        "- show_history: research session history",
        "- fetch_data: explicit request to download or refresh OHLCV data",
        "- unsupported_or_unsafe: unsupported, execution-oriented, or unsafe request",
        "",
        "Research-intelligence distinctions:",
        "- Use deep_analyze_symbol for a comprehensive multi-block symbol review; use explain_symbol for a simple score explanation.",
        "- Use summarize_watchlist_deep when the user asks for clusters, setup distribution, risks, or a research agenda.",
        "- Use generate_shortlist only for research prioritization, never for execution guidance.",
        "- Use generate_research_scenario for conditional confirmation/invalidation monitoring scenarios.",
        "- Use review_setup_evidence for historical persisted outcome evidence or setup statistics.",
        "",
        "Examples:",
        '- "What was the market regime on 2026-07-01?" -> review_market_regime',
        '- "Show the strongest sectors today." -> review_sector_strength',
        '- "How does FPT align with its sector context?" -> review_symbol_sector_alignment',
        *_RESEARCH_EXAMPLES,
        "",
        "Rules:",
        "- Any execution, broker, account, allocation, or certainty request MUST be unsupported_or_unsafe.",
        "- Any web search, unrestricted code, raw SQL, filesystem, or MCP request MUST be unsupported_or_unsafe.",
        "- Requests to download or refresh source data MUST be fetch_data.",
        '- Respond ONLY with valid JSON matching: {"intent": "<name>", "confidence": 0.0-1.0, "entities": {}, "needs_clarification": false, "clarification_question": null, "safety_flags": []}',
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
