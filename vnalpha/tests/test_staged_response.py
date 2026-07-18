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
    from vnalpha.assistant.models import ToolPlanStep

    fake_answer = AssistantAnswer(
        summary="VPB price is 18,500.",
        basis="Market data",
        risks_caveats="",
        tool_trace_summary="",
    )
    fake_plan = AssistantPlan(
        intent="lookup",
        steps=[
            ToolPlanStep(
                step_id="s1",
                tool_name="candidate.explain",
                arguments={"symbol": "VPB"},
                purpose="get price",
                required_permission="READ_DATA",
            )
        ],
    )

    controller = ChatController(
        on_message=_on_message,
        connection_factory=lambda: MagicMock(),
    )

    with (
        patch(
            "vnalpha.chat.controller.ChatController._run_ask",
            return_value=(fake_answer, fake_plan),
        ),
        patch("vnalpha.observability.audit.log_audit") as log_audit,
    ):
        controller.handle_natural_language("What is VPB price?")

    assert all(
        "What is VPB price?" not in str(call) for call in log_audit.call_args_list
    )

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

    from vnalpha.assistant.models import ToolPlanStep

    fake_answer = AssistantAnswer(
        summary="Result.",
        basis="Market data",
        risks_caveats="",
        tool_trace_summary="",
    )
    fake_plan = AssistantPlan(
        intent="lookup",
        steps=[
            ToolPlanStep(
                step_id="s1",
                tool_name="watchlist.scan",
                arguments={},
                purpose="scan",
                required_permission="READ_DATA",
            )
        ],
    )

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


def test_prepared_turn_runs_tools_before_synthesizing_and_final() -> None:
    from types import SimpleNamespace

    from vnalpha.assistant.models import AssistantAnswer, AssistantPlan, ToolPlanStep
    from vnalpha.chat.controller import ChatController
    from vnalpha.tools.executor import TraceEvent

    timeline: list[str] = []
    plan = AssistantPlan(
        intent="lookup",
        steps=[
            ToolPlanStep(
                step_id="s1",
                tool_name="watchlist.scan",
                arguments={},
                purpose="scan",
                required_permission="READ_DATA",
            )
        ],
    )
    answer = AssistantAnswer(
        summary="Prepared result.",
        basis="Persisted data",
        risks_caveats="",
        tool_trace_summary="",
    )

    def on_message(_style: str, text: str) -> None:
        for stage in ("classifying", "planning", "synthesizing"):
            if stage in text:
                timeline.append(stage)
                return
        if "Prepared result." in text:
            if "final" not in timeline:
                timeline.append("final")

    def on_trace(event: TraceEvent) -> None:
        timeline.append(event.status)

    controller = ChatController(
        on_message=on_message,
        on_trace=on_trace,
        connection_factory=lambda: MagicMock(),
    )
    controller._prepare_turn = MagicMock(return_value=SimpleNamespace(plan=plan))

    def execute(_prepared: object):
        assert controller._on_trace is not None
        controller._on_trace(TraceEvent("watchlist.scan", "RUNNING", None, "t1"))
        controller._on_trace(TraceEvent("watchlist.scan", "SUCCESS", 1.0, "t1"))
        return answer, plan

    controller._execute_prepared_turn = execute

    controller.handle_natural_language("Show candidates")

    assert timeline == [
        "classifying",
        "planning",
        "RUNNING",
        "SUCCESS",
        "synthesizing",
        "final",
    ]


def test_failed_prepared_turn_omits_success_and_synthesizing() -> None:
    from types import SimpleNamespace

    from vnalpha.assistant.models import AssistantPlan, ToolPlanStep
    from vnalpha.chat.controller import ChatController
    from vnalpha.tools.executor import TraceEvent

    timeline: list[str] = []
    plan = AssistantPlan(
        intent="deep_analyze_symbol",
        steps=[
            ToolPlanStep(
                step_id="s1",
                tool_name="data.ensure_current_symbol",
                arguments={"symbol": "FPT"},
                purpose="provision",
                required_permission="WRITE_DATA",
            )
        ],
    )

    def on_message(_style: str, text: str) -> None:
        for stage in ("classifying", "planning", "synthesizing"):
            if stage in text:
                timeline.append(stage)

    def on_trace(event: TraceEvent) -> None:
        timeline.append(event.status)

    controller = ChatController(
        on_message=on_message,
        on_trace=on_trace,
        connection_factory=lambda: MagicMock(),
    )
    controller._prepare_turn = MagicMock(return_value=SimpleNamespace(plan=plan))

    def execute(_prepared: object):
        assert controller._on_trace is not None
        controller._on_trace(
            TraceEvent("data.ensure_current_symbol", "RUNNING", None, "t1")
        )
        controller._on_trace(
            TraceEvent("data.ensure_current_symbol", "FAILED", 1.0, "t1")
        )
        raise RuntimeError("readiness was not achieved")

    controller._execute_prepared_turn = execute

    controller.handle_natural_language("Analyze FPT")

    assert timeline == ["classifying", "planning", "RUNNING", "FAILED"]
