from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.panel import Panel

from vnalpha.assistant.models import AssistantAnswer, AssistantPlan, ToolPlanStep
from vnalpha.assistant.presentation_projection import attach_assistant_presentation
from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ResultArtifact,
    ResultColumn,
    ResultPanel,
    ResultTable,
)
from vnalpha.tui.models.conversation import AssistantAnswerMessage
from vnalpha.tui.result_presentation import (
    assistant_result_presentation,
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


def test_watchlist_tool_results_render_as_bounded_safe_tui_tables() -> None:
    candidate = {
        "rank": 1,
        "symbol": "FPT",
        "score": 0.81234,
        "candidate_class": "STRONG_CANDIDATE",
        "setup_type": "MOMENTUM_CONTINUATION",
        "risk_flags_json": '["LOW_LIQUIDITY", "[red]VOLATILE[/red]"]',
        "data_quality_status": "READY",
        "api_key": "must-not-render",
        "raw_json": {"provider": "must-not-render"},
    }
    cases = (
        ("watchlist.scan", {"data": [candidate]}, "Watchlist · 2026-07-24"),
        (
            "watchlist.filter",
            {"data": [candidate]},
            "Filtered watchlist · 2026-07-24",
        ),
        (
            "watchlist.summarize_deep",
            {"data": {"as_of_date": "2026-07-23", "top_candidates": [candidate]}},
            "Watchlist top candidates · 2026-07-23",
        ),
    )

    scan_answer = None
    for index, (tool_name, output, expected_title) in enumerate(cases, start=1):
        step = ToolPlanStep(
            step_id=f"step-{index}",
            tool_name=tool_name,
            arguments={"date": "2026-07-24"},
            purpose="show persisted watchlist",
            required_permission="read_watchlist",
        )
        plan = AssistantPlan(intent="scan_candidates", steps=[step])
        answer = attach_assistant_presentation(
            AssistantAnswer(
                "One candidate.",
                "Persisted watchlist.",
                "Review risk flags.",
                "done",
            ),
            plan,
            {step.step_id: output},
        )
        table = answer.research_metadata["presentation"]["tables"][0]
        assert str(table["title"]).startswith(expected_title)
        assert table["rows"] == [
            [
                "1",
                "FPT",
                "0.812",
                "STRONG_CANDIDATE",
                "MOMENTUM_CONTINUATION",
                "LOW_LIQUIDITY, VOLATILE",
                "READY",
            ]
        ]
        scan_answer = scan_answer or answer

    assert scan_answer is not None
    message = AssistantAnswerMessage(
        text=scan_answer.summary,
        summary=scan_answer.summary,
        basis=scan_answer.basis,
        risks_caveats=scan_answer.risks_caveats,
        research_metadata=scan_answer.research_metadata,
    )
    presentation = assistant_result_presentation(message)
    buffer = StringIO()
    Console(file=buffer, width=180, color_system=None, highlight=False).print(
        presentation.body
    )
    rendered = buffer.getvalue()

    assert "Rank" in rendered and "FPT" in rendered and "0.812" in rendered
    assert "LOW_LIQUIDITY, VOLATILE" in rendered
    assert (
        "Rank\tSymbol\tScore\tClass\tSetup\tRisk flags\tQuality"
        in presentation.plain_text
    )
    assert "must-not-render" not in rendered + presentation.plain_text
    assert "[red]" not in rendered + presentation.plain_text

    malformed = assistant_result_presentation(
        AssistantAnswerMessage(
            text="Fallback prose.",
            summary="Fallback prose.",
            research_metadata={
                "presentation": {"schema_version": 999, "tables": ["invalid"]}
            },
        )
    )
    assert "Rank\tSymbol" not in malformed.plain_text
