"""Tests for Phase 5.9 intent classifier and plan builder."""

from __future__ import annotations

import json

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


# ===========================================================================
# Plan builder tests
# ===========================================================================
