"""Tests for Section 7 (Streaming/staged response UX) — AssistantStageEvent model,
stage helpers, and ChatController staged emission."""

from __future__ import annotations

from vnalpha.chat.events import AssistantStage

# ---------------------------------------------------------------------------
# events module — unit tests
# ---------------------------------------------------------------------------


def test_assistant_stage_has_all_seven_values():
    """AssistantStage enum must expose exactly the 7 documented lifecycle stages."""

    expected = {
        "classifying",
        "planning",
        "tool_start",
        "tool_success",
        "tool_failed",
        "synthesizing",
        "final",
    }
    actual = {s.value for s in AssistantStage}
    assert actual == expected


# ---------------------------------------------------------------------------
# __init__.py re-exports
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ChatController staged emission
# ---------------------------------------------------------------------------
