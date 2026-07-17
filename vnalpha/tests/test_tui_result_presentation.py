from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ResultArtifact,
    ResultColumn,
    ResultPanel,
    ResultTable,
)
from vnalpha.tui.models.conversation import AssistantAnswerMessage
from vnalpha.tui.research_navigation import (
    ArtifactDetailState,
    artifact_detail_renderable,
)
from vnalpha.tui.result_presentation import (
    assistant_result_presentation,
    command_result_presentation,
    operational_result_presentation,
)


def test_command_presentation_keeps_rich_and_exact_plain_forms() -> None:
    result = CommandResult(
        status=CommandStatus.SUCCESS,
        title="FPT analysis",
        summary="Persisted evidence only.",
        tables=[
            ResultTable(
                title="Signals",
                columns=[
                    ResultColumn("name", "Signal"),
                    ResultColumn("value", "Value"),
                ],
                rows=[["RS20", 1.25], ["Setup", None]],
            )
        ],
        panels=[ResultPanel("Quality", {"status": "READY"})],
        artifacts=[ResultArtifact("analysis:FPT:2026-07-15", {"safe": True})],
        metadata={"subject": "FPT", "as_of_date": "2026-07-15"},
    )

    presentation = command_result_presentation("/analyze FPT", result)

    assert isinstance(presentation.body, Panel)
    assert presentation.kind == "command"
    assert presentation.title == "FPT analysis"
    assert presentation.metadata["subject"] == "FPT"
    assert presentation.plain_text == (
        "FPT analysis\n"
        "Status: SUCCESS\n"
        "Command: /analyze FPT\n"
        "Symbol: FPT\n"
        "As of: 2026-07-15\n"
        "Persisted evidence only.\n"
        "Signals\n"
        "Signal\tValue\n"
        "RS20\t1.25\n"
        "Setup\t—\n"
        "Quality\n"
        "status: READY\n"
        "Artifacts\n"
        "analysis:FPT:2026-07-15"
    )


def test_assistant_presentation_uses_same_result_contract() -> None:
    message = AssistantAnswerMessage(
        text="[bold]not markup[/bold]",
        summary="[bold]not markup[/bold]",
        basis="canonical warehouse",
        risks_caveats="Missing latest filing.",
        missing_data=["filing"],
        grounded_source_refs=["canonical_ohlcv:FPT:2026-07-15"],
        research_metadata={"symbol": "FPT", "as_of_date": "2026-07-15"},
    )

    presentation = assistant_result_presentation(message)

    assert isinstance(presentation.body, Panel)
    assert presentation.kind == "assistant"
    assert "[bold]" not in presentation.plain_text
    assert "not markup" in presentation.plain_text
    assert "Symbol: FPT" in presentation.plain_text
    assert "Grounded source refs" in presentation.plain_text
    assert presentation.body.border_style == "yellow"


def test_plain_result_redacts_controls_and_sensitive_values() -> None:
    result = CommandResult(
        status=CommandStatus.SUCCESS,
        title="Result\x1b[31m",
        summary="Authorization: Bearer live-secret api_key=also-secret [red]safe[/red]",
    )

    presentation = command_result_presentation("/quality", result)

    assert "\x1b" not in presentation.plain_text
    assert "live-secret" not in presentation.plain_text
    assert "also-secret" not in presentation.plain_text
    assert "[red]" not in presentation.plain_text
    assert "[REDACTED]" in presentation.plain_text


def test_nested_sensitive_mapping_is_redacted_in_rich_and_plain_forms() -> None:
    result = CommandResult(
        status=CommandStatus.SUCCESS,
        title="Safe result",
        panels=[
            ResultPanel(
                "Diagnostics",
                {"context": {"credentials": {"api_key": "live-secret"}}},
            )
        ],
    )
    presentation = command_result_presentation("/quality", result)
    console = Console(record=True, width=80)

    console.print(presentation.body)
    rendered = console.export_text()

    assert "live-secret" not in presentation.plain_text
    assert "live-secret" not in rendered
    assert "[REDACTED]" in presentation.plain_text
    assert "[REDACTED]" in rendered


def test_sensitive_table_columns_and_metadata_are_redacted() -> None:
    credential = "super" + "secret"
    result = CommandResult(
        status=CommandStatus.SUCCESS,
        title="Safe result",
        tables=[
            ResultTable(
                title="Credentials",
                columns=[
                    ResultColumn("client_secret", "Client secret"),
                    ResultColumn("FIINQUANT_PASSWORD", "Provider password"),
                    ResultColumn("value", "Value"),
                ],
                rows=[[credential, credential, "safe"]],
            )
        ],
        metadata={"private_key": credential, "VNALPHA_LLM_API_KEY": credential},
    )
    presentation = command_result_presentation("/quality", result)
    console = Console(record=True, width=80)

    console.print(presentation.body)
    rendered = console.export_text()

    assert credential not in presentation.plain_text
    assert credential not in rendered
    assert presentation.metadata["private_key"] == "[REDACTED]"
    assert presentation.metadata["VNALPHA_LLM_API_KEY"] == "[REDACTED]"


def test_unbroken_help_usage_folds_without_ellipsis() -> None:
    result = CommandResult(
        status=CommandStatus.SUCCESS,
        title="Help",
        tables=[
            ResultTable(
                title="Commands",
                columns=[ResultColumn("usage", "Usage")],
                rows=[["/todo <list|add|done|block|clear-done> [text|id]"]],
            )
        ],
    )
    presentation = command_result_presentation("/help", result)
    console = Console(record=True, width=30)

    console.print(presentation.body)
    rendered = console.export_text()

    assert "…" not in rendered
    assert "clear-done" in "".join(rendered.split())


def test_operational_result_uses_canonical_plain_and_bordered_forms() -> None:
    credential = "live-" + "secret"
    presentation = operational_result_presentation(
        "/logs errors --latest",
        f"[2026-07-16] [ERROR] api_key={credential} failed",
    )
    console = Console(record=True, width=80)

    console.print(presentation.body)
    rendered = console.export_text()

    assert presentation.kind == "operational"
    assert "[2026-07-16] [ERROR]" in presentation.plain_text
    assert credential not in presentation.plain_text
    assert credential not in rendered


def test_artifact_detail_documents_the_actual_copy_command() -> None:
    state = ArtifactDetailState(
        artifact_id="analysis:FPT",
        command="/analyze FPT",
        title="FPT",
        subject="FPT",
        result=CommandResult(status="SUCCESS", title="FPT"),
        note_command=None,
        assistant_prompt="Review FPT",
    )
    console = Console(record=True, width=100)

    console.print(artifact_detail_renderable(state))
    rendered = console.export_text()

    assert "/copy artifact-id" in rendered
    assert "Ctrl+Y artifact id" not in rendered
