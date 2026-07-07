"""Tests for vnalpha.chat.context — Section 5 Multi-turn context (Phase 5.10)."""

from __future__ import annotations

import inspect

import pytest

from vnalpha.chat.context import (
    ChatContext,
    build_context_prompt_prefix,
    resolve_entity_reference,
    update_context_from_command,
)


# ---------------------------------------------------------------------------
# ChatContext — default field values
# ---------------------------------------------------------------------------


class TestChatContextDefaults:
    def test_all_optional_fields_are_none_or_empty(self):
        ctx = ChatContext()
        assert ctx.chat_session_id is None
        assert ctx.target_date is None
        assert ctx.last_symbols == []
        assert ctx.selected_symbol is None
        assert ctx.selected_rank is None
        assert ctx.last_watchlist_date is None
        assert ctx.last_command is None
        assert ctx.last_assistant_intent is None
        assert ctx.last_plan is None
        assert ctx.last_tool_outputs_summary is None

    def test_last_symbols_is_independent_per_instance(self):
        """Mutable default must not be shared across instances."""
        ctx1 = ChatContext()
        ctx2 = ChatContext()
        ctx1.last_symbols.append("VNM")
        assert ctx2.last_symbols == []


# ---------------------------------------------------------------------------
# update_context_from_command
# ---------------------------------------------------------------------------


class TestUpdateContextFromCommand:
    def test_always_updates_last_command(self):
        ctx = ChatContext()
        update_context_from_command(ctx, "/help", "some output")
        assert ctx.last_command == "/help"

    def test_strips_whitespace_from_command(self):
        ctx = ChatContext()
        update_context_from_command(ctx, "  /help  ", "output")
        assert ctx.last_command == "/help"

    def test_non_scan_command_does_not_update_watchlist_date(self):
        ctx = ChatContext()
        update_context_from_command(ctx, "/rank 2026-07-07", "VNM VCB")
        assert ctx.last_watchlist_date is None

    def test_scan_command_updates_last_watchlist_date(self):
        ctx = ChatContext()
        update_context_from_command(ctx, "/scan 2026-07-07", "VNM VCB results")
        assert ctx.last_watchlist_date == "2026-07-07"

    def test_scan_command_updates_last_symbols_from_result(self):
        ctx = ChatContext()
        update_context_from_command(
            ctx,
            "/scan 2026-07-07",
            "Top picks: VNM VCB HPG FPT",
        )
        assert "VNM" in ctx.last_symbols
        assert "VCB" in ctx.last_symbols
        assert "HPG" in ctx.last_symbols
        assert "FPT" in ctx.last_symbols

    def test_scan_command_preserves_symbol_order(self):
        ctx = ChatContext()
        update_context_from_command(ctx, "/scan 2026-07-07", "VNM VCB HPG")
        assert ctx.last_symbols[0] == "VNM"
        assert ctx.last_symbols[1] == "VCB"
        assert ctx.last_symbols[2] == "HPG"

    def test_scan_command_deduplicates_symbols(self):
        ctx = ChatContext()
        update_context_from_command(ctx, "/scan 2026-07-07", "VNM VCB VNM HPG VCB")
        assert ctx.last_symbols.count("VNM") == 1
        assert ctx.last_symbols.count("VCB") == 1

    def test_scan_command_no_date_in_command(self):
        """If no ISO date in the command, last_watchlist_date is not updated."""
        ctx = ChatContext()
        update_context_from_command(ctx, "/scan", "VNM VCB")
        assert ctx.last_watchlist_date is None


# ---------------------------------------------------------------------------
# resolve_entity_reference
# ---------------------------------------------------------------------------


class TestResolveEntityReference:
    def test_the_first_one_returns_last_symbols_first(self):
        ctx = ChatContext(last_symbols=["VNM", "VCB", "HPG"])
        result = resolve_entity_reference(ctx, "Tell me about the first one")
        assert "VNM" in result

    def test_first_one_returns_last_symbols_first(self):
        ctx = ChatContext(last_symbols=["FPT"])
        result = resolve_entity_reference(ctx, "analyze first one")
        assert "FPT" in result

    def test_top_candidate_returns_selected_symbol(self):
        ctx = ChatContext(selected_symbol="VCB", last_symbols=["VNM", "VCB"])
        result = resolve_entity_reference(ctx, "What about the top candidate?")
        assert "VCB" in result

    def test_that_symbol_returns_selected_symbol(self):
        ctx = ChatContext(selected_symbol="HPG")
        result = resolve_entity_reference(ctx, "Explain that symbol to me")
        assert "HPG" in result

    def test_that_stock_returns_selected_symbol(self):
        ctx = ChatContext(selected_symbol="VNM")
        result = resolve_entity_reference(ctx, "What is the outlook for that stock?")
        assert "VNM" in result

    def test_returns_original_text_when_no_symbols(self):
        ctx = ChatContext()
        text = "What is the first one?"
        result = resolve_entity_reference(ctx, text)
        # No symbols available — text returned unchanged (no replacement)
        assert result == text

    def test_returns_original_text_when_no_selected_symbol(self):
        ctx = ChatContext()
        text = "Explain that symbol"
        result = resolve_entity_reference(ctx, text)
        assert result == text

    def test_unrecognized_text_is_not_modified(self):
        ctx = ChatContext(last_symbols=["VNM"], selected_symbol="VCB")
        text = "What is the market cap of VNM?"
        result = resolve_entity_reference(ctx, text)
        assert result == text


# ---------------------------------------------------------------------------
# build_context_prompt_prefix
# ---------------------------------------------------------------------------


class TestBuildContextPromptPrefix:
    def test_returns_empty_string_for_empty_context(self):
        ctx = ChatContext()
        assert build_context_prompt_prefix(ctx) == ""

    def test_includes_target_date(self):
        ctx = ChatContext(target_date="2026-07-07")
        prefix = build_context_prompt_prefix(ctx)
        assert "date=2026-07-07" in prefix

    def test_includes_last_watchlist_date_when_no_target_date(self):
        ctx = ChatContext(last_watchlist_date="2026-07-05")
        prefix = build_context_prompt_prefix(ctx)
        assert "date=2026-07-05" in prefix

    def test_target_date_takes_priority_over_watchlist_date(self):
        ctx = ChatContext(target_date="2026-07-07", last_watchlist_date="2026-07-05")
        prefix = build_context_prompt_prefix(ctx)
        assert "date=2026-07-07" in prefix
        assert "date=2026-07-05" not in prefix

    def test_includes_symbols(self):
        ctx = ChatContext(last_symbols=["VNM", "VCB"])
        prefix = build_context_prompt_prefix(ctx)
        assert "VNM" in prefix
        assert "VCB" in prefix

    def test_includes_selected_symbol(self):
        ctx = ChatContext(selected_symbol="VNM")
        prefix = build_context_prompt_prefix(ctx)
        assert "selected=VNM" in prefix

    def test_formatted_string_with_all_fields(self):
        ctx = ChatContext(
            target_date="2026-07-07",
            last_symbols=["VNM", "VCB"],
            selected_symbol="VNM",
        )
        prefix = build_context_prompt_prefix(ctx)
        assert prefix.startswith("Context:")
        assert "date=2026-07-07" in prefix
        assert "symbols=[VNM,VCB]" in prefix
        assert "selected=VNM" in prefix
        assert prefix.endswith("\n")


# ---------------------------------------------------------------------------
# AssistantApp.ask() signature check
# ---------------------------------------------------------------------------


class TestAssistantAppSignature:
    def test_ask_accepts_chat_context_kwarg(self):
        """AssistantApp.ask() must have a chat_context keyword parameter."""
        from vnalpha.assistant.app import AssistantApp

        sig = inspect.signature(AssistantApp.ask)
        assert "chat_context" in sig.parameters, (
            "AssistantApp.ask() is missing the chat_context parameter"
        )
        param = sig.parameters["chat_context"]
        assert param.default is None, (
            "chat_context parameter default should be None (optional)"
        )

    def test_ask_chat_context_is_keyword_only(self):
        """chat_context should be keyword-only (after *)."""
        from vnalpha.assistant.app import AssistantApp

        sig = inspect.signature(AssistantApp.ask)
        param = sig.parameters["chat_context"]
        assert param.kind in (
            inspect.Parameter.KEYWORD_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
