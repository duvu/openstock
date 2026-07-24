"""Tests for Phase 5.9 intent classifier and plan builder."""

from __future__ import annotations

import json

import pytest

from vnalpha.assistant.errors import IntentClassificationError
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.intent import (
    IntentClassifier,
    _deterministic_precheck,
)
from vnalpha.assistant.models import (
    IntentResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_response(
    intent: str, confidence: float = 0.9, entities: dict | None = None, **kwargs
) -> tuple[str, dict]:
    payload = {
        "intent": intent,
        "confidence": confidence,
        "entities": entities or {},
        "needs_clarification": kwargs.get("needs_clarification", False),
        "clarification_question": kwargs.get("clarification_question"),
        "safety_flags": kwargs.get("safety_flags", []),
    }
    return json.dumps(payload), {}


def _make_classifier(
    responses: list[tuple[str, dict]] | None = None,
) -> IntentClassifier:
    return IntentClassifier(FakeLLMClient(responses))


def _make_intent(intent: str, entities: dict | None = None) -> IntentResult:
    return IntentResult(intent=intent, confidence=0.9, entities=entities or {})


# ===========================================================================
# Intent classifier tests
# ===========================================================================


class TestDeterministicPrecheck:
    def test_deterministic_precheck_buy_refused(self):
        result = _deterministic_precheck("Buy FPT now")
        assert result == "TRADING_EXECUTION"


class TestIntentClassifierWatchlistFallback:
    def test_watchlist_fallback_for_classifier_failures(self):
        class FailingGateway:
            last_raw_responses: tuple[dict, ...] = ()

            def chat(self, *_args, **_kwargs):
                raise RuntimeError("gateway unavailable")

        class FailingParseGateway:
            last_raw_responses: tuple[dict, ...] = ()

            def __init__(self) -> None:
                self.calls = 0

            def chat(self, *_args, **_kwargs):
                self.calls += 1
                return "NO-JSON", {}

        fallback_classifier = IntentClassifier(FailingGateway())
        for prompt, expected_intent in {
            "watchlist": "scan_candidates",
            "watchlist summary": "summarize_watchlist_deep",
            "phan tich co phieu FPT": "deep_analyze_symbol",
            "Phan tich co phieu fpt": "deep_analyze_symbol",
        }.items():
            result = fallback_classifier.classify(prompt)
            assert result.intent == expected_intent
            assert result.confidence == pytest.approx(0.95)
            if expected_intent == "deep_analyze_symbol":
                assert result.entities == {"symbol": "FPT"}
            else:
                assert result.entities == {}

        parse_failure_classifier = IntentClassifier(FailingParseGateway())
        result = parse_failure_classifier.classify("Summarize watchlist in depth")
        assert result.intent == "summarize_watchlist_deep"
        assert result.confidence == pytest.approx(0.95)

        parse_failure_analyze = parse_failure_classifier.classify(
            "phan tich co phieu FPT"
        )
        assert parse_failure_analyze.intent == "deep_analyze_symbol"
        assert parse_failure_analyze.entities == {"symbol": "FPT"}
        assert parse_failure_analyze.confidence == pytest.approx(0.95)

        strict_classifier = IntentClassifier(FailingGateway())
        with pytest.raises(IntentClassificationError):
            strict_classifier.classify("thi truong hom nay")


# ===========================================================================
# Plan builder tests
# ===========================================================================
