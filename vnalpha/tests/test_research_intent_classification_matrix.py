from __future__ import annotations

import json

import pytest

from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.intent import IntentClassifier


@pytest.mark.parametrize(
    ("intent", "prompt", "entities"),
    [
        (
            "deep_analyze_symbol",
            "Give me a deep research review of FPT.",
            {"symbol": "FPT"},
        ),
        (
            "review_market_regime",
            "Review the persisted market regime.",
            {"date": "2026-07-10"},
        ),
        (
            "review_sector_strength",
            "Show persisted sector strength.",
            {"date": "2026-07-10"},
        ),
        (
            "summarize_watchlist_deep",
            "Summarize the watchlist structure and risks in depth.",
            {"date": "2026-07-10"},
        ),
        (
            "generate_shortlist",
            "Create a research-priority shortlist.",
            {"date": "2026-07-10", "top": 5},
        ),
        (
            "generate_research_scenario",
            "Build a conditional research scenario for FPT.",
            {"symbol": "FPT"},
        ),
        (
            "review_setup_evidence",
            "Review persisted evidence for MOMENTUM_CONTINUATION.",
            {"setup_type": "MOMENTUM_CONTINUATION"},
        ),
    ],
)
def test_every_research_intent_is_supported_by_classifier(
    intent: str,
    prompt: str,
    entities: dict,
):
    response = json.dumps(
        {
            "intent": intent,
            "confidence": 0.95,
            "entities": entities,
            "needs_clarification": False,
            "clarification_question": None,
            "safety_flags": [],
        }
    )
    classifier = IntentClassifier(FakeLLMClient(responses=[(response, {})]))

    result = classifier.classify(prompt)

    assert result.intent == intent
    assert result.entities == entities
