from __future__ import annotations

from rich.panel import Panel

from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ResultArtifact,
    ResultColumn,
    ResultPanel,
    ResultTable,
)
from vnalpha.tui.result_presentation import (
    command_result_presentation,
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
