"""Tests for Section 7 (Streaming/staged response UX) — AssistantStageEvent model,
stage helpers, and ChatController staged emission."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# events module — unit tests
# ---------------------------------------------------------------------------


def test_assistant_stage_has_all_seven_values():
    """AssistantStage enum must expose exactly the 7 documented lifecycle stages."""
    from vnalpha.chat.events import AssistantStage

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


def test_stage_to_style_returns_correct_mapping():
    """stage_to_style must return the documented Rich markup style for each stage."""
    from vnalpha.chat.events import AssistantStage, stage_to_style

    assert stage_to_style(AssistantStage.CLASSIFYING) == "dim cyan"
    assert stage_to_style(AssistantStage.PLANNING) == "bold cyan"
    assert stage_to_style(AssistantStage.TOOL_START) == "dim"
    assert stage_to_style(AssistantStage.TOOL_SUCCESS) == "green"
    assert stage_to_style(AssistantStage.TOOL_FAILED) == "red"
    assert stage_to_style(AssistantStage.SYNTHESIZING) == "dim cyan"
    assert stage_to_style(AssistantStage.FINAL) == "bold"


def test_format_stage_event_tool_start():
    """TOOL_START events render as '⟳ {tool_name} running...'."""
    from vnalpha.chat.events import (
        AssistantStage,
        AssistantStageEvent,
        format_stage_event,
    )

    event = AssistantStageEvent(
        stage=AssistantStage.TOOL_START,
        text="",
        tool_name="get_price",
    )
    assert format_stage_event(event) == "⟳ get_price running..."


def test_format_stage_event_tool_success():
    """TOOL_SUCCESS events render as '✓ {tool_name} success {elapsed_ms}ms'."""
    from vnalpha.chat.events import (
        AssistantStage,
        AssistantStageEvent,
        format_stage_event,
    )

    event = AssistantStageEvent(
        stage=AssistantStage.TOOL_SUCCESS,
        text="",
        tool_name="get_price",
        elapsed_ms=42,
    )
    assert format_stage_event(event) == "✓ get_price success 42ms"


def test_format_stage_event_tool_failed():
    """TOOL_FAILED events render as '✗ {tool_name} failed {elapsed_ms}ms'."""
    from vnalpha.chat.events import (
        AssistantStage,
        AssistantStageEvent,
        format_stage_event,
    )

    event = AssistantStageEvent(
        stage=AssistantStage.TOOL_FAILED,
        text="",
        tool_name="get_price",
        elapsed_ms=18,
    )
    assert format_stage_event(event) == "✗ get_price failed 18ms"


def test_format_stage_event_classifying():
    """CLASSIFYING events render as '⋯ classifying...'."""
    from vnalpha.chat.events import (
        AssistantStage,
        AssistantStageEvent,
        format_stage_event,
    )

    event = AssistantStageEvent(stage=AssistantStage.CLASSIFYING, text="")
    assert format_stage_event(event) == "⋯ classifying..."


def test_format_stage_event_planning():
    """PLANNING events render as '⋯ planning...'."""
    from vnalpha.chat.events import (
        AssistantStage,
        AssistantStageEvent,
        format_stage_event,
    )

    event = AssistantStageEvent(stage=AssistantStage.PLANNING, text="")
    assert format_stage_event(event) == "⋯ planning..."


def test_format_stage_event_synthesizing():
    """SYNTHESIZING events render as '⋯ synthesizing...'."""
    from vnalpha.chat.events import (
        AssistantStage,
        AssistantStageEvent,
        format_stage_event,
    )

    event = AssistantStageEvent(stage=AssistantStage.SYNTHESIZING, text="")
    assert format_stage_event(event) == "⋯ synthesizing..."


def test_format_stage_event_final_returns_text():
    """FINAL events return event.text directly."""
    from vnalpha.chat.events import (
        AssistantStage,
        AssistantStageEvent,
        format_stage_event,
    )

    answer = "VPB closed at 18,500 VND."
    event = AssistantStageEvent(stage=AssistantStage.FINAL, text=answer)
    assert format_stage_event(event) == answer


# ---------------------------------------------------------------------------
# __init__.py re-exports
# ---------------------------------------------------------------------------


def test_chat_package_exports():
    """AssistantStage, AssistantStageEvent, format_stage_event exported from vnalpha.chat."""
    import vnalpha.chat as chat_pkg

    assert hasattr(chat_pkg, "AssistantStage")
    assert hasattr(chat_pkg, "AssistantStageEvent")
    assert hasattr(chat_pkg, "format_stage_event")
    assert hasattr(chat_pkg, "stage_to_style")


# ---------------------------------------------------------------------------
# ChatController staged emission
# ---------------------------------------------------------------------------


def test_handle_natural_language_emits_classifying_and_final():
    """handle_natural_language must emit CLASSIFYING then FINAL (at minimum) via on_message.

    AssistantApp.ask() is fully mocked — no real LLM calls.
    """
    from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
    from vnalpha.chat.controller import ChatController

    messages: list[tuple[str, str]] = []

    def _on_message(style: str, text: str) -> None:
        messages.append((style, text))

    # Build a minimal fake answer
    fake_answer = AssistantAnswer(
        summary="VPB price is 18,500.",
        basis="Market data",
        risks_caveats="",
        tool_trace_summary="",
    )
    fake_plan = AssistantPlan(intent="lookup", steps=[])

    controller = ChatController(
        on_message=_on_message,
        connection_factory=lambda: MagicMock(),
    )

    with patch(
        "vnalpha.chat.controller.ChatController._run_ask",
        return_value=(fake_answer, fake_plan),
    ):
        controller.handle_natural_language("What is VPB price?")

    styles = [style for style, _ in messages]
    texts = [text for _, text in messages]

    # CLASSIFYING must appear before FINAL
    assert "dim cyan" in styles, f"Expected 'dim cyan' (CLASSIFYING) in {styles}"
    assert "bold" in styles, f"Expected 'bold' (FINAL) in {styles}"

    classifying_idx = next(
        i for i, (s, t) in enumerate(messages) if s == "dim cyan" and "classifying" in t
    )
    final_idx = next(
        i for i, (s, t) in enumerate(messages) if s == "bold" and "VPB" in t
    )
    assert classifying_idx < final_idx, "CLASSIFYING must precede FINAL"

    # The final message should contain the answer summary
    assert any("VPB price is 18,500." in t for t in texts), (
        f"Answer summary not found in {texts}"
    )


def test_handle_natural_language_emits_planning_and_synthesizing():
    """PLANNING and SYNTHESIZING stages are emitted between CLASSIFYING and FINAL."""
    from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
    from vnalpha.chat.controller import ChatController

    messages: list[tuple[str, str]] = []

    def _on_message(style: str, text: str) -> None:
        messages.append((style, text))

    fake_answer = AssistantAnswer(
        summary="Result.",
        basis="Market data",
        risks_caveats="",
        tool_trace_summary="",
    )
    fake_plan = AssistantPlan(intent="lookup", steps=[])

    controller = ChatController(
        on_message=_on_message,
        connection_factory=lambda: MagicMock(),
    )

    with patch(
        "vnalpha.chat.controller.ChatController._run_ask",
        return_value=(fake_answer, fake_plan),
    ):
        controller.handle_natural_language("Some question")

    stage_texts = [text for _, text in messages]

    assert "⋯ classifying..." in stage_texts
    assert "⋯ planning..." in stage_texts
    assert "⋯ synthesizing..." in stage_texts
