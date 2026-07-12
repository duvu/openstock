from __future__ import annotations

import pytest

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
