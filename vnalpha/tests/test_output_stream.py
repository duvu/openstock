from __future__ import annotations

import pytest

from vnalpha.commands.models import CommandResult, CommandStatus, ResultArtifact
from vnalpha.tui.models.conversation import AssistantAnswerMessage, UserMessage
from vnalpha.tui.result_presentation import command_result_presentation
from vnalpha.tui.widgets.output_stream import OutputStream


def test_transcript_is_unboxed_so_result_blocks_own_visual_emphasis() -> None:
    assert "border: round" not in OutputStream.DEFAULT_CSS


def test_safe_text_escapes_rich_markup() -> None:
    output = OutputStream()
    escaped = output._safe_text("[bold red]SYSTEM ERROR[/bold red]")

    assert str(escaped) == "\\[bold red]SYSTEM ERROR\\[/bold red]"


def test_generic_transcript_boundary_redacts_inline_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = OutputStream()
    writes: list[object] = []
    monkeypatch.setattr(
        OutputStream,
        "_write",
        lambda self, text, **kwargs: writes.append(text),
        raising=False,
    )

    output.show_error("request failed api_key=super-secret", source="router")

    assert "super-secret" not in output.transcript_text()
    assert "[REDACTED]" in output.transcript_text()
    assert all("super-secret" not in str(rendered) for rendered in writes)


def test_user_input_marksup_is_rendered_as_literal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = OutputStream()
    writes: list[object] = []
    monkeypatch.setattr(
        OutputStream,
        "_write",
        lambda self, text, **kwargs: writes.append(text),
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
        lambda self, text, **kwargs: writes.append(text),
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
    assert output.latest_result_text().endswith(
        "Summary: danger\nRisks: No explicit caveats.\nSources: 0  Missing data: 0"
    )
    assert "[red]" not in output.latest_result_text()


def test_assistant_answer_message_truncates_to_max_messages() -> None:
    output = OutputStream(max_messages=50)
    for idx in range(1, 55):
        output.append_message(UserMessage(f"msg-{idx}"))

    messages = output.render_messages()
    assert len(messages) == 50
    assert str(messages[0].text) == "msg-5"
    assert str(messages[-1].text) == "msg-54"


def test_output_stream_retains_canonical_result_and_transcript_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = OutputStream()
    monkeypatch.setattr(
        OutputStream, "_write", lambda self, text, **kwargs: None, raising=False
    )
    result = CommandResult(
        status=CommandStatus.SUCCESS,
        title="FPT analysis",
        summary="Grounded result.",
        metadata={"subject": "FPT", "as_of_date": "2026-07-15"},
    )
    presentation = command_result_presentation("/analyze FPT", result)

    output.show_user_input("/analyze FPT", prompt_type="slash")
    output.show_result(presentation)

    assert output.latest_result_text() == presentation.plain_text
    assert output.transcript_text() == f"$ /analyze FPT\n\n{presentation.plain_text}"


def test_assistant_final_updates_latest_result_without_scraping_rich_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = OutputStream()
    monkeypatch.setattr(
        OutputStream, "_write", lambda self, text, **kwargs: None, raising=False
    )

    output.append_assistant_answer(
        AssistantAnswerMessage(
            text="Evidence-backed answer.",
            summary="Evidence-backed answer.",
            grounded_source_refs=["score:FPT:2026-07-15"],
        )
    )

    assert output.latest_result_text().startswith("Assistant research answer\n")
    assert output.transcript_text() == output.latest_result_text()


def test_failed_command_does_not_replace_latest_copyable_result() -> None:
    output = OutputStream()
    successful = command_result_presentation(
        "/analyze FPT",
        CommandResult(status="SUCCESS", title="Successful analysis"),
    )
    failed = command_result_presentation(
        "/analyze BAD",
        CommandResult(status="FAILED", title="Failed analysis"),
    )

    output.show_result(successful)
    output.show_result(failed)

    assert output.latest_result_text() == successful.plain_text
    assert "Failed analysis" in output.transcript_text()


def test_artifact_navigation_helpers_expose_current_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = OutputStream()
    writes: list[object] = []
    monkeypatch.setattr(
        OutputStream,
        "_write",
        lambda self, text, **kwargs: writes.append(text),
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
        assert before == [
            "Workspace resumed: ws-123",
            "$ /analyze FPT",
            "rendered result",
        ]

        assert output.open_latest_artifact_detail() is True
        await pilot.pause()
        assert output.current_artifact_id() == "analysis.deep_symbol:FPT:2026-07-12"

        assert output.navigate_back() is True
        await pilot.pause()

        assert _lines(log) == before


@pytest.mark.asyncio
async def test_new_message_after_artifact_detail_retains_result_presentation() -> None:
    pytest.importorskip("textual")

    from textual.app import App, ComposeResult
    from textual.widgets import RichLog

    class ProbeApp(App):
        def compose(self) -> ComposeResult:
            yield OutputStream(id="output-stream")

    result = CommandResult(
        status="SUCCESS",
        title="FPT retained analysis",
        summary="Grounded result remains visible.",
        artifacts=[ResultArtifact(name="analysis:FPT", data={"available": True})],
        metadata={"subject": "FPT"},
    )

    async with ProbeApp().run_test(headless=True, size=(120, 30)) as pilot:
        output = pilot.app.query_one(OutputStream)
        output.show_result(command_result_presentation("/analyze FPT", result))
        output.register_command_result("/analyze FPT", result)
        assert output.open_latest_artifact_detail() is True
        await pilot.pause()

        output.append_message(UserMessage("follow-up"))
        await pilot.pause()

        log = pilot.app.query_one(RichLog)
        rendered = "\n".join(line.text for line in log.lines)
        assert "FPT retained analysis" in rendered
        assert "follow-up" in rendered


@pytest.mark.asyncio
async def test_rendered_transcript_has_bounded_line_retention() -> None:
    pytest.importorskip("textual")

    from textual.app import App, ComposeResult
    from textual.widgets import RichLog

    class ProbeApp(App):
        def compose(self) -> ComposeResult:
            yield OutputStream(max_messages=50)

    async with ProbeApp().run_test(headless=True) as pilot:
        log = pilot.app.query_one(RichLog)

        assert log.max_lines == 1000
