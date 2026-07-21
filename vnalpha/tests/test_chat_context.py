"""Tests for vnalpha.chat.context — Section 5 Multi-turn context (Phase 5.10)."""

from __future__ import annotations

from vnalpha.chat.context import (
    ChatContext,
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


# ---------------------------------------------------------------------------
# update_context_from_command
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# resolve_entity_reference
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# build_context_prompt_prefix
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# AssistantApp.ask() signature check
# ---------------------------------------------------------------------------
