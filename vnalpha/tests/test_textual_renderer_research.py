from __future__ import annotations

from io import StringIO

from rich.console import Console

from vnalpha.commands.models import (
    CommandResult,
    ResultArtifact,
    ResultColumn,
    ResultPanel,
    ResultTable,
)
from vnalpha.commands.renderers.textual_renderer import result_to_markup


def _render(result: CommandResult) -> str:
    buffer = StringIO()
    Console(file=buffer, highlight=False).print(result_to_markup(result))
    return buffer.getvalue()


def test_deep_analysis_renderer_surfaces_workflow_metadata() -> None:
    result = CommandResult(
        status="PARTIAL",
        title="/analyze — FPT",
        summary="Deep persisted research context for FPT.",
        panels=[
            ResultPanel(
                title="Trend and momentum",
                content={"candidate_class": "STRONG_CANDIDATE", "score": "0.820"},
            ),
            ResultPanel(
                title="Volatility and levels",
                content={"support_20d": "120.000", "resistance_20d": "130.000"},
            ),
        ],
        artifacts=[
            ResultArtifact(
                name="analysis.deep_symbol:FPT:2026-07-12",
                data={"available": True},
            )
        ],
        metadata={
            "artifact_id": "analysis.deep_symbol:FPT:2026-07-12",
            "subject": "FPT",
            "workflow_status": "partial",
            "missing_data": ["sector_strength_snapshot"],
            "artifact_refs": ["candidate_score:FPT:2026-07-12"],
        },
        warnings=["No persisted sector strength snapshot was available."],
    )

    rendered = _render(result)

    assert "Workflow status" in rendered
    assert "analysis.deep_symbol:FPT:2026-07-12" in rendered
    assert "Trend and momentum" in rendered
    assert "Volatility and levels" in rendered


def test_scenario_renderer_surfaces_branch_table() -> None:
    result = CommandResult(
        status="SUCCESS",
        title="/research-plan — FPT",
        summary="Generated a conditional research scenario for FPT.",
        tables=[
            ResultTable(
                title="Scenario branches",
                columns=[
                    ResultColumn("name", "Branch"),
                    ResultColumn("conditions", "Conditions"),
                    ResultColumn("interpretation", "Interpretation"),
                ],
                rows=[["confirmation", "close >= resistance", "setup remains valid"]],
            )
        ],
        metadata={
            "artifact_id": "scenario.generate_research_plan:FPT:2026-07-12",
            "subject": "FPT",
            "workflow_status": "complete",
        },
    )

    rendered = _render(result)

    assert "Scenario branches" in rendered
    assert "confirmation" in rendered
    assert "scenario.generate_research_plan:FPT:2026-07-12" in rendered


def test_setup_evidence_renderer_surfaces_artifacts_and_metrics() -> None:
    result = CommandResult(
        status="SUCCESS",
        title="/setup-evidence — ACCUMULATION_BASE",
        summary="Persisted setup evidence for ACCUMULATION_BASE.",
        tables=[
            ResultTable(
                title="Historical outcome metrics",
                columns=[
                    ResultColumn("metric", "Metric"),
                    ResultColumn("value", "Value"),
                ],
                rows=[["hit_rate", "62.0%"], ["avg_forward_return", "0.041"]],
            )
        ],
        artifacts=[
            ResultArtifact(
                name="evidence.get_setup_history:ACCUMULATION_BASE:20:2026-07-12",
                data={"available": True},
            )
        ],
        metadata={
            "artifact_id": "evidence.get_setup_history:ACCUMULATION_BASE:20:2026-07-12",
            "subject": "ACCUMULATION_BASE",
            "workflow_status": "complete",
        },
    )

    rendered = _render(result)

    assert "Historical outcome metrics" in rendered
    assert "hit_rate" in rendered
    assert "Artifacts" in rendered
