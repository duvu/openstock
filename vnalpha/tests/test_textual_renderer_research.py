from __future__ import annotations

from io import StringIO

from rich.console import Console

from vnalpha.commands.models import (
    CommandResult,
    ResultArtifact,
    ResultPanel,
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
