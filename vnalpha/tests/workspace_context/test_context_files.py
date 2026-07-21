from __future__ import annotations

from vnalpha.workspace_context.integration import (
    render_context_markdown,
)
from vnalpha.workspace_context.models import (
    WorkspaceArtifactRef,
    WorkspaceInputRef,
    WorkspaceState,
    WorkspaceTask,
)


def _sample_state() -> WorkspaceState:
    return WorkspaceState(
        workspace_id="ws-20260709-001",
        title="FPT workflow",
        status="active",
        mode="research",
        created_at="2026-07-09T01:00:00+00:00",
        updated_at="2026-07-09T02:00:00+00:00",
        active_date="2026-07-09",
        active_symbols=["FPT", "HPG"],
        active_artifacts=[
            WorkspaceArtifactRef(
                artifact_id="watchlist-1",
                artifact_type="watchlist",
                path="artifacts/watchlist.json",
                summary="Daily shortlist",
                created_at="2026-07-09T01:30:00+00:00",
                source_refs=["candidate_score:FPT:2026-07-09"],
            )
        ],
        recent_inputs=[
            WorkspaceInputRef(
                input_id="input-1",
                input_kind="user",
                summary="Compare FPT and HPG",
                redaction_status="redacted",
                created_at="2026-07-09T01:10:00+00:00",
                source="tui",
                content="Compare FPT and HPG",
                metadata={"length": 19},
            )
        ],
        open_tasks=[
            WorkspaceTask(
                task_id="task-1",
                text="Review breakout evidence",
                status="open",
                priority="high",
                created_at="2026-07-09T01:40:00+00:00",
                updated_at="2026-07-09T01:40:00+00:00",
            )
        ],
        assumptions=["Fresh warehouse data remains authoritative."],
        warnings=["compact recommended"],
        errors=[],
        data_freshness={"warehouse": "fresh"},
        context_size={"events": 3, "inputs": 1},
    )


def test_render_context_markdown_includes_core_sections() -> None:
    rendered = render_context_markdown(_sample_state())

    assert rendered.startswith("# Workspace Context")
    assert "Workspace ID: `ws-20260709-001`" in rendered
    assert "## Active Symbols" in rendered
    assert "- `FPT`" in rendered
    assert "## Open Tasks" in rendered
    assert "Review breakout evidence" in rendered
    assert "## Recent Inputs" in rendered
    assert "Compare FPT and HPG" in rendered
    assert "## Artifacts" in rendered
    assert "Daily shortlist" in rendered
    assert "## Assumptions" in rendered
