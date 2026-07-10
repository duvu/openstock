"""Tests for Phase 5.9 intent classifier and plan builder."""

from __future__ import annotations

import json

import pytest

from vnalpha.assistant.errors import (
    IntentClassificationError,
    PlanValidationError,
)
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.intent import IntentClassifier, _deterministic_precheck
from vnalpha.assistant.models import AssistantPlan, IntentResult, ToolPlanStep
from vnalpha.assistant.planner import PlanBuilder, _validate_plan
from vnalpha.assistant.tool_policy import SAFE_TOOLS

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

    def test_deterministic_precheck_sell_refused(self):
        result = _deterministic_precheck("Sell all VNM shares")
        assert result == "TRADING_EXECUTION"

    def test_deterministic_precheck_broker_refused(self):
        result = _deterministic_precheck("Connect to my broker account")
        assert result == "TRADING_EXECUTION"

    def test_deterministic_precheck_portfolio_refused(self):
        result = _deterministic_precheck("Show my portfolio performance")
        assert result == "TRADING_EXECUTION"

    def test_deterministic_precheck_safe_passes(self):
        result = _deterministic_precheck("Show strongest candidates today")
        assert result is None


class TestIntentClassifier:
    def test_deterministic_buy_returns_unsafe_result(self):
        classifier = _make_classifier()
        result = classifier.classify("Buy FPT now")
        assert result.intent == "unsupported_or_unsafe"
        assert result.confidence == 1.0
        assert "TRADING_EXECUTION" in result.safety_flags

    def test_deterministic_sell_returns_unsafe_result(self):
        classifier = _make_classifier()
        result = classifier.classify("Sell VNM shares immediately")
        assert result.intent == "unsupported_or_unsafe"
        assert result.confidence == 1.0
        assert "TRADING_EXECUTION" in result.safety_flags

    def test_deterministic_broker_returns_unsafe_result(self):
        classifier = _make_classifier()
        result = classifier.classify("Open broker account for me")
        assert result.intent == "unsupported_or_unsafe"
        assert result.confidence == 1.0

    def test_deterministic_portfolio_returns_unsafe_result(self):
        classifier = _make_classifier()
        result = classifier.classify("Manage my portfolio positions")
        assert result.intent == "unsupported_or_unsafe"
        assert result.confidence == 1.0

    def test_deterministic_precheck_safe_passes_to_llm(self):
        """Safe prompt should call the LLM, not be blocked by precheck."""
        responses = [_fake_response("scan_candidates", 0.95)]
        classifier = _make_classifier(responses)
        result = classifier.classify("Show strongest candidates")
        assert result.intent == "scan_candidates"
        assert len(classifier._client.calls) == 1

    def test_llm_classification_scan_candidates(self):
        responses = [_fake_response("scan_candidates", 0.95)]
        classifier = _make_classifier(responses)
        result = classifier.classify("List top research candidates for today")
        assert result.intent == "scan_candidates"
        assert result.confidence == 0.95

    def test_llm_classification_explain_symbol(self):
        responses = [_fake_response("explain_symbol", 0.88, entities={"symbol": "FPT"})]
        classifier = _make_classifier(responses)
        result = classifier.classify("Why is FPT on the watchlist?")
        assert result.intent == "explain_symbol"
        assert result.entities.get("symbol") == "FPT"

    def test_llm_classification_unsupported_normalized(self):
        """Unknown intent returned by LLM should be normalised to unsupported_or_unsafe."""
        responses = [_fake_response("totally_unknown_intent", 0.7)]
        classifier = _make_classifier(responses)
        result = classifier.classify("Do something weird")
        assert result.intent == "unsupported_or_unsafe"

    def test_llm_invalid_json_raises_classification_error(self):
        fake = FakeLLMClient()

        # Override chat to return invalid JSON
        def bad_chat(messages, response_schema=None, *, stage="unknown"):
            return "not valid json {{{{", {}

        fake.chat = bad_chat  # type: ignore[method-assign]
        classifier = IntentClassifier(fake)
        with pytest.raises(IntentClassificationError, match="Invalid JSON"):
            classifier.classify("Show me something")

    def test_classifier_populates_entities(self):
        entities = {"symbol": "VNM", "date": "2025-01-15"}
        responses = [_fake_response("explain_symbol", 0.9, entities=entities)]
        classifier = _make_classifier(responses)
        result = classifier.classify("Explain VNM on 2025-01-15")
        assert result.entities["symbol"] == "VNM"
        assert result.entities["date"] == "2025-01-15"


# ===========================================================================
# Plan builder tests
# ===========================================================================


class TestPlanBuilder:
    def setup_method(self):
        self.builder = PlanBuilder()

    def test_plan_scan_has_watchlist_scan_tool(self):
        intent = _make_intent("scan_candidates")
        plan = self.builder.build(intent)
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "watchlist.scan"

    def test_plan_compare_has_two_steps(self):
        intent = _make_intent("compare_symbols", {"symbols": ["FPT", "VNM"]})
        plan = self.builder.build(intent)
        assert len(plan.steps) == 2
        tool_names = [s.tool_name for s in plan.steps]
        assert "candidate.compare" in tool_names
        # Multi-symbol compare uses get_many_status
        assert "quality.get_many_status" in tool_names

    def test_plan_compare_single_symbol_uses_get_status(self):
        """Single-symbol compare uses quality.get_status, not get_many_status."""
        intent = _make_intent("compare_symbols", {"symbols": ["FPT"]})
        plan = self.builder.build(intent)
        tool_names = [s.tool_name for s in plan.steps]
        assert "quality.get_status" in tool_names
        assert "quality.get_many_status" not in tool_names

    def test_plan_compare_multi_symbol_passes_symbols_list(self):
        """Multi-symbol compare passes full symbols list to get_many_status."""
        intent = _make_intent("compare_symbols", {"symbols": ["FPT", "VNM", "HPG"]})
        plan = self.builder.build(intent)
        quality_step = next(
            s for s in plan.steps if s.tool_name == "quality.get_many_status"
        )
        assert quality_step.arguments.get("symbols") == ["FPT", "VNM", "HPG"]

    def test_plan_explain_has_three_steps(self):
        intent = _make_intent("explain_symbol", {"symbol": "FPT"})
        plan = self.builder.build(intent)
        assert len(plan.steps) == 3
        tool_names = [s.tool_name for s in plan.steps]
        assert "candidate.explain" in tool_names
        assert "lineage.get_symbol_lineage" in tool_names
        assert "quality.get_status" in tool_names

    def test_plan_refusal_is_refusal(self):
        intent = _make_intent("unsupported_or_unsafe")
        plan = self.builder.build(intent)
        assert plan.is_refusal()

    def test_plan_refusal_no_steps(self):
        intent = _make_intent("unsupported_or_unsafe")
        plan = self.builder.build(intent)
        assert plan.steps == []

    def test_plan_history_tool_name(self):
        intent = _make_intent("show_history")
        plan = self.builder.build(intent)
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "history.list_sessions"

    def test_plan_note_tool_name(self):
        intent = _make_intent(
            "create_research_note", {"symbol": "FPT", "note_text": "Good setup"}
        )
        plan = self.builder.build(intent)
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "note.create"

    def test_plan_quality_tool_name(self):
        intent = _make_intent("review_quality", {"symbol": "VNM"})
        plan = self.builder.build(intent)
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "quality.get_status"

    def test_plan_lineage_tool_name(self):
        intent = _make_intent("show_lineage", {"symbol": "HPG"})
        plan = self.builder.build(intent)
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "lineage.get_symbol_lineage"

    def test_fetch_data_intent_is_refused_with_explicit_command_guidance(self):
        # Given: an assistant request to mutate warehouse data
        # When: the deterministic planner builds the fetch_data intent
        # Then: it returns a refusal rather than an autonomous data.fetch step
        plan = self.builder.build(_make_intent("fetch_data", {"symbol": "FPT"}))
        assert plan.is_refusal()
        assert plan.steps == []
        assert plan.refusal_reason is not None
        assert "explicit" in plan.refusal_reason.lower()

    def test_validation_rejects_unknown_tool(self):
        bad_step = ToolPlanStep(
            step_id="abc12345",
            tool_name="broker.execute_trade",
            arguments={"symbol": "FPT", "qty": 100},
            purpose="Execute a trade",
            required_permission="BROKER_EXECUTION",
        )
        bad_plan = AssistantPlan(
            intent="scan_candidates",
            steps=[bad_step],
        )
        with pytest.raises(PlanValidationError, match="not allowed"):
            _validate_plan(bad_plan)

    def test_preview_includes_intent_and_steps(self):
        intent = _make_intent("scan_candidates")
        plan = self.builder.build(intent)
        preview = self.builder.preview(plan)
        assert "scan_candidates" in preview
        assert "watchlist.scan" in preview
        assert "Steps:" in preview

    def test_preview_refusal_shows_refused(self):
        intent = _make_intent("unsupported_or_unsafe")
        plan = self.builder.build(intent)
        preview = self.builder.preview(plan)
        assert preview.startswith("[REFUSED]")

    def test_plan_filter_candidates(self):
        intent = _make_intent(
            "filter_candidates", {"filters": {"class": "STRONG_CANDIDATE"}}
        )
        plan = self.builder.build(intent)
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "watchlist.filter"

    def test_plan_summarize_watchlist(self):
        intent = _make_intent("summarize_watchlist")
        plan = self.builder.build(intent)
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "watchlist.scan"

    def test_plan_all_steps_in_canonical_policy(self):
        for intent_name in [
            "scan_candidates",
            "filter_candidates",
            "compare_symbols",
            "explain_symbol",
            "review_quality",
            "show_lineage",
            "summarize_watchlist",
            "create_research_note",
            "show_history",
        ]:
            intent = _make_intent(intent_name)
            plan = self.builder.build(intent)
            for step in plan.steps:
                assert step.tool_name in SAFE_TOOLS, (
                    f"Intent '{intent_name}' produced non-canonical tool '{step.tool_name}'"
                )

    def test_plan_step_ids_are_unique(self):
        """Each step in a multi-step plan must have a unique step_id."""
        intent = _make_intent("explain_symbol", {"symbol": "FPT"})
        plan = self.builder.build(intent)
        ids = [s.step_id for s in plan.steps]
        assert len(ids) == len(set(ids))

    def test_plan_refusal_default_reason(self):
        intent = _make_intent("unsupported_or_unsafe")
        plan = self.builder.build(intent)
        assert plan.refusal_reason is not None
        assert len(plan.refusal_reason) > 0

    def test_plan_refusal_custom_reason(self):
        intent = _make_intent(
            "unsupported_or_unsafe", {"reason": "Trading not allowed"}
        )
        plan = self.builder.build(intent)
        assert plan.refusal_reason == "Trading not allowed"

    def test_validation_passes_for_refusal_plan(self):
        """Refusal plans bypass tool validation (no steps to check)."""
        plan = AssistantPlan(
            intent="unsupported_or_unsafe",
            steps=[],
            refusal_reason="Not allowed",
        )
        # Should not raise
        _validate_plan(plan)
