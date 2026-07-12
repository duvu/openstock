from __future__ import annotations

import pytest

from vnalpha.commands.models import CommandResult, ResultArtifact
from vnalpha.tui.models.conversation import AssistantAnswerMessage, UserMessage
from vnalpha.tui.widgets.output_stream import OutputStream


def test_safe_text_escapes_rich_markup() -> None:
    output = OutputStream()
    escaped = output._safe_text("[bold red]SYSTEM ERROR[/bold red]")

    assert str(escaped) == "\\[bold red]SYSTEM ERROR\\[/bold red]"


def test_user_input_marksup_is_rendered_as_literal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = OutputStream()
    writes: list[object] = []
    monkeypatch.setattr(
        OutputStream,
        "_write",
        lambda self, text: writes.append(text),
        raising=False,
    )

    output.show_user_input("[bold red]SYSTEM ERROR[/bold red]")

    assert writes
    assert "\\[bold red]SYSTEM ERROR\\[/bold red]" in str(writes[-1])


def test_assistant_answer_markup_is_rendered_as_literal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = OutputStream()
    writes: list[object] = []
    monkeypatch.setattr(
        OutputStream,
        "_write",
        lambda self, text: writes.append(text),
        raising=False,
    )

    output.append_message(
        AssistantAnswerMessage(
            text="[red]danger[/red]",
            summary="[red]danger[/red]",
            risks_caveats="",
        )
    )

    assert writes
    assert any("\\[red]danger\\[/red]" in str(w) for w in writes)


def test_assistant_answer_message_truncates_to_max_messages() -> None:
    output = OutputStream(max_messages=50)
    for idx in range(1, 55):
        output.append_message(UserMessage(f"msg-{idx}"))

    messages = output.render_messages()
    assert len(messages) == 50
    assert str(messages[0].text) == "msg-5"
    assert str(messages[-1].text) == "msg-54"


def test_artifact_navigation_helpers_expose_current_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = OutputStream()
    writes: list[object] = []
    monkeypatch.setattr(
        OutputStream,
        "_write",
        lambda self, text: writes.append(text),
        raising=False,
    )
    monkeypatch.setattr(
        OutputStream,
        "clear_visible",
        lambda self: writes.append("cleared"),
        raising=False,
    )

    result = CommandResult(
        status="SUCCESS",
        title="/analyze — FPT",
        summary="Deep persisted research context for FPT.",
        artifacts=[
            ResultArtifact(
                name="analysis.deep_symbol:FPT:2026-07-12",
                data={"available": True},
            )
        ],
        metadata={
            "subject": "FPT",
            "artifact_id": "analysis.deep_symbol:FPT:2026-07-12",
        },
    )

    output.register_command_result("/analyze FPT", result)

    assert output.open_latest_artifact_detail() is True
    assert output.current_artifact_id() == "analysis.deep_symbol:FPT:2026-07-12"
    assert output.note_command_for_current_artifact() is not None
    assert "/note FPT" in output.note_command_for_current_artifact()
    assert output.assistant_prompt_for_current_artifact() is not None
    assert "analysis.deep_symbol:FPT:2026-07-12" in (
        output.assistant_prompt_for_current_artifact() or ""
    )
    assert output.navigate_back() is True
    assert writes


@pytest.mark.asyncio
async def test_artifact_navigation_restores_visible_transcript() -> None:
    pytest.importorskip("textual")

    from textual.app import App, ComposeResult
    from textual.widgets import RichLog

    class ProbeApp(App):
        def compose(self) -> ComposeResult:
            yield OutputStream(id="output-stream")

    def _lines(log: RichLog) -> list[str]:
        return [
            getattr(line, "plain", getattr(line, "text", str(line)))
            for line in log.lines
        ]

    result = CommandResult(
        status="SUCCESS",
        title="/analyze — FPT",
        summary="Deep persisted research context for FPT.",
        artifacts=[
            ResultArtifact(
                name="analysis.deep_symbol:FPT:2026-07-12",
                data={"available": True},
            )
        ],
        metadata={
            "subject": "FPT",
            "artifact_id": "analysis.deep_symbol:FPT:2026-07-12",
        },
    )

    async with ProbeApp().run_test(headless=True) as pilot:
        output = pilot.app.query_one("#output-stream", OutputStream)
        log = pilot.app.query_one("#output-log", RichLog)

        output.show_assistant_message("Workspace resumed: ws-123")
        output.show_command_result("/analyze FPT", "rendered result")
        output.register_command_result("/analyze FPT", result)
        await pilot.pause()

        before = _lines(log)
        assert before == ["Workspace resumed: ws-123", "$ /analyze FPT", "rendered result"]

        assert output.open_latest_artifact_detail() is True
        await pilot.pause()
        assert output.current_artifact_id() == "analysis.deep_symbol:FPT:2026-07-12"

        assert output.navigate_back() is True
        await pilot.pause()

        assert _lines(log) == before
