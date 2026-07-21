"""Issue #315 — canonicalize symbol entities before planning and provisioning.

Covers the required regression matrix: the shared normalizer, the classifier
parser, the deterministic planner, and the tool/provisioning boundary. The same
prompt ``phan tich co phieu fpt`` must always resolve to canonical ``FPT``, all
equivalent classifier shapes must yield the same plan and tool arguments, and
malformed shapes must fail typed ``INVALID_SYMBOL_FORMAT`` validation before any
warehouse work — distinct from ``SYMBOL_NOT_FOUND`` membership failures.
"""

from __future__ import annotations

import json

import pytest

from vnalpha.assistant.errors import AssistantInputValidationError
from vnalpha.assistant.models import IntentResult
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.assistant.response_json import parse_classifier_response
from vnalpha.core.symbols import (
    INVALID_SYMBOL_FORMAT,
    SYMBOL_NOT_FOUND,
    CanonicalSymbols,
    SymbolFormatError,
    canonicalize_symbol_entities,
    is_valid_ticker,
    validate_ticker,
)

# ---------------------------------------------------------------------------
# Shared normalizer / validator
# ---------------------------------------------------------------------------


class TestSharedNormalizer:
    @pytest.mark.parametrize(
        "value",
        ["FPT", "fpt", " fpt ", "Fpt"],
    )
    def test_validate_ticker_uppercases_and_trims(self, value: str) -> None:
        assert validate_ticker(value) == "FPT"

    def test_validate_ticker_allows_digits_after_first_letter(self) -> None:
        assert validate_ticker("e1vfvn30") == "E1VFVN30"

    @pytest.mark.parametrize(
        "value",
        [
            "['FPT']",
            '["FPT"]',
            "FPT,VCB",
            "[FPT, VCB]",
            "FPT VCB",
            "1FPT",
            "",
            "   ",
            "F",
            "TOOLONGSYMBOL12",
            {"ticker": "FPT"},
            ["FPT"],
            123,
            None,
        ],
    )
    def test_validate_ticker_rejects_non_ticker(self, value: object) -> None:
        with pytest.raises(SymbolFormatError):
            validate_ticker(value)

    def test_format_error_carries_stable_category(self) -> None:
        try:
            validate_ticker("['FPT']")
        except SymbolFormatError as exc:
            assert exc.category == INVALID_SYMBOL_FORMAT
            assert INVALID_SYMBOL_FORMAT in str(exc)
        else:  # pragma: no cover - defensive
            pytest.fail("expected SymbolFormatError")

    def test_format_and_membership_categories_are_distinct(self) -> None:
        assert INVALID_SYMBOL_FORMAT != SYMBOL_NOT_FOUND

    def test_is_valid_ticker(self) -> None:
        assert is_valid_ticker("FPT")
        assert not is_valid_ticker("fpt")  # not yet uppercased
        assert not is_valid_ticker("['FPT']")
        assert not is_valid_ticker(["FPT"])

    @pytest.mark.parametrize(
        "entities",
        [
            {"symbol": "FPT"},
            {"symbols": ["FPT"]},
            {"symbol": ["FPT"]},
            {"symbol": "['FPT']"},
            {"symbol": '["FPT"]'},
            {"symbol": " fpt "},
        ],
    )
    def test_accepted_shapes_resolve_to_single_fpt(self, entities: dict) -> None:
        canonical = canonicalize_symbol_entities(entities)
        assert canonical.primary_symbol == "FPT"
        assert canonical.symbols == ("FPT",)

    def test_marker_prefix_in_symbols_collapses_to_ticker(self) -> None:
        # A leading "co phieu" marker kept in the symbols list ("CP", "FPT")
        # collapses to the real ticker.
        canonical = canonicalize_symbol_entities({"symbols": ["CP", "FPT"]})
        assert canonical.primary_symbol == "FPT"
        assert canonical.symbols == ("FPT",)

    def test_empty_shape_resolves_to_none(self) -> None:
        canonical = canonicalize_symbol_entities({"symbol": None, "symbols": []})
        assert canonical == CanonicalSymbols(symbols=(), primary_symbol=None)

    def test_duplicates_and_whitespace_are_collapsed(self) -> None:
        canonical = canonicalize_symbol_entities(
            {"symbols": [" fpt ", "FPT", "vcb", "VCB"]}
        )
        assert canonical.symbols == ("FPT", "VCB")
        assert canonical.primary_symbol == "FPT"

    def test_multi_symbol_order_preserved(self) -> None:
        canonical = canonicalize_symbol_entities({"symbols": ["VCB", "FPT", "HPG"]})
        assert canonical.symbols == ("VCB", "FPT", "HPG")

    @pytest.mark.parametrize(
        "entities",
        [
            {"symbol": {"ticker": "FPT"}},
            {"symbol": "FPT,VCB"},
            {"symbol": "[FPT, VCB]"},
            {"symbol": "FPT/VCB"},
            {"symbol": 42},
        ],
    )
    def test_malformed_shapes_rejected(self, entities: dict) -> None:
        with pytest.raises(SymbolFormatError):
            canonicalize_symbol_entities(entities)

    def test_contradictory_symbol_and_symbols_rejected(self) -> None:
        with pytest.raises(SymbolFormatError):
            canonicalize_symbol_entities({"symbol": "VCB", "symbols": ["FPT"]})


# ---------------------------------------------------------------------------
# Classifier parser
# ---------------------------------------------------------------------------


def _classify(intent: str, entities: dict, prompt: str = "") -> IntentResult:
    payload = json.dumps({"intent": intent, "entities": entities})
    return parse_classifier_response(payload, user_prompt=prompt)


class TestParserCanonicalization:
    def test_empty_entities_with_cued_prompt_recovers(self) -> None:
        parsed = _classify("deep_analyze_symbol", {}, prompt="phan tich co phieu fpt")
        assert parsed.entities["symbol"] == "FPT"
        assert parsed.entities["symbols"] == ["FPT"]

    @pytest.mark.parametrize(
        "entities",
        [
            {"symbol": "FPT"},
            {"symbols": ["FPT"]},
            {"symbol": ["FPT"]},
            {"symbol": "['FPT']"},
            {"symbol": '["FPT"]'},
        ],
    )
    def test_equivalent_shapes_produce_same_canonical_entities(
        self, entities: dict
    ) -> None:
        parsed = _classify("deep_analyze_symbol", entities)
        assert parsed.entities["symbol"] == "FPT"
        assert parsed.entities["symbols"] == ["FPT"]

    def test_duplicates_and_whitespace_normalized(self) -> None:
        parsed = _classify("compare_symbols", {"symbols": [" fpt ", "FPT", "vcb"]})
        assert parsed.entities["symbols"] == ["FPT", "VCB"]

    @pytest.mark.parametrize(
        "entities",
        [
            {"symbol": {"ticker": "FPT"}},
            {"symbol": "FPT,VCB"},
            {"symbol": "[FPT, VCB]"},
        ],
    )
    def test_malformed_shapes_raise_typed_validation(self, entities: dict) -> None:
        with pytest.raises(AssistantInputValidationError, match=INVALID_SYMBOL_FORMAT):
            _classify("deep_analyze_symbol", entities)

    def test_contradiction_raises_typed_validation(self) -> None:
        with pytest.raises(AssistantInputValidationError, match=INVALID_SYMBOL_FORMAT):
            _classify("deep_analyze_symbol", {"symbol": "VCB", "symbols": ["FPT"]})

    def test_stopword_only_prompt_does_not_recover(self) -> None:
        parsed = _classify(
            "deep_analyze_symbol", {}, prompt="top nganh ngan hang hom nay"
        )
        assert not parsed.entities.get("symbol")
        assert not parsed.entities.get("symbols")

    def test_non_symbol_intent_is_untouched(self) -> None:
        parsed = _classify("scan_candidates", {"symbol": "['FPT']"})
        # Non-symbol intents never canonicalize, so the raw shape is preserved
        # and never fails validation here.
        assert parsed.entities["symbol"] == "['FPT']"


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


def _plan(intent: str, entities: dict):
    return PlanBuilder().build(
        IntentResult(intent=intent, confidence=0.9, entities=entities)
    )


class TestPlannerCanonicalArguments:
    def test_deep_analysis_canonical_plan(self) -> None:
        plan = _plan("deep_analyze_symbol", {"symbol": "FPT", "symbols": ["FPT"]})
        assert [step.tool_name for step in plan.steps] == [
            "data.ensure_current_symbol",
            "analysis.deep_symbol",
        ]
        for step in plan.steps:
            assert step.arguments["symbol"] == "FPT"

    def test_missing_symbol_refusal_reason(self) -> None:
        plan = _plan("deep_analyze_symbol", {})
        assert plan.is_refusal()
        assert (
            plan.refusal_reason == "The deep_analyze_symbol workflow requires a symbol."
        )

    @pytest.mark.parametrize(
        "entities",
        [
            {"symbol": "FPT"},
            {"symbols": ["FPT"]},
            {"symbol": "FPT", "symbols": ["FPT"]},
        ],
    )
    def test_equivalent_shapes_produce_equivalent_steps(self, entities: dict) -> None:
        plan = _plan("deep_analyze_symbol", entities)
        args = [step.arguments["symbol"] for step in plan.steps]
        assert args == ["FPT", "FPT"]

    def test_planner_never_emits_list_or_quoted_literal(self) -> None:
        # Even if a raw list shape reaches the planner directly, it resolves to
        # the canonical scalar ticker, never a "['FPT']" literal.
        plan = _plan("deep_analyze_symbol", {"symbol": ["FPT"]})
        assert plan.steps[0].arguments["symbol"] == "FPT"

    def test_multi_symbol_ordering_preserved(self) -> None:
        plan = _plan("compare_symbols", {"symbols": ["VCB", "FPT", "HPG"]})
        compare_step = next(s for s in plan.steps if s.tool_name == "candidate.compare")
        assert compare_step.arguments["symbols"] == ["VCB", "FPT", "HPG"]

    def test_compare_single_symbol_unchanged(self) -> None:
        plan = _plan("compare_symbols", {"symbols": ["FPT"]})
        tool_names = [s.tool_name for s in plan.steps]
        assert "quality.get_status" in tool_names
        assert "quality.get_many_status" not in tool_names


# ---------------------------------------------------------------------------
# Tool boundary
# ---------------------------------------------------------------------------


class TestToolBoundaryValidation:
    @pytest.mark.parametrize(
        "bad_symbol",
        ["['FPT']", '["FPT"]', "FPT,VCB", "[FPT, VCB]", "1FPT", "FP T"],
    )
    def test_malformed_ticker_rejected_before_warehouse(self, bad_symbol: str) -> None:
        from vnalpha.tools.ensure_current_symbol import ensure_current_symbol
        from vnalpha.tools.errors import ToolExecutionError

        # conn is never touched: validation happens before any DB access, so a
        # sentinel object that raises on use proves no warehouse work occurred.
        class _ExplodingConn:
            def __getattr__(self, name):  # pragma: no cover - must not run
                raise AssertionError("warehouse must not be touched for bad ticker")

        with pytest.raises(ToolExecutionError, match=INVALID_SYMBOL_FORMAT):
            ensure_current_symbol(_ExplodingConn(), bad_symbol)

    def test_application_op_rejects_malformed_before_lock(self) -> None:
        from vnalpha.data_provisioning.ensure_current_symbol import (
            ProvisioningOutcome,
            ensure_current_symbol_ready,
        )

        class _ExplodingConn:
            def __getattr__(self, name):  # pragma: no cover - must not run
                raise AssertionError("warehouse must not be touched for bad ticker")

        result = ensure_current_symbol_ready(_ExplodingConn(), "['FPT']")
        assert result.outcome is ProvisioningOutcome.FAILED
        assert not result.is_ready
        assert result.actions
        assert result.actions[0].failure_category == INVALID_SYMBOL_FORMAT
        assert INVALID_SYMBOL_FORMAT in result.errors[0]

    def test_empty_symbol_is_missing_not_format_error(self) -> None:
        from vnalpha.tools.ensure_current_symbol import ensure_current_symbol
        from vnalpha.tools.errors import ToolExecutionError

        with pytest.raises(ToolExecutionError, match="requires 'symbol'"):
            ensure_current_symbol(object(), "   ")
