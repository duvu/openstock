from __future__ import annotations

from vnalpha.workspace_context.integration import (
    build_workspace_context_prompt_prefix,
)
from vnalpha.workspace_context.models import WorkspaceArtifactRef


def _artifact(number: int) -> WorkspaceArtifactRef:
    return WorkspaceArtifactRef(
        artifact_id=f"artifact-{number}",
        artifact_type="report",
        path=f"artifacts/report-{number}.md",
        summary=f"summary-{number}-" + "x" * 80,
        created_at="2026-07-10T00:00:00+00:00",
    )


def test_workspace_context_returns_empty_when_workspace_is_missing(tmp_path):
    # Given: an empty workspace root
    # When: assistant context is requested for an unknown workspace
    context = build_workspace_context_prompt_prefix("missing", root=tmp_path)

    # Then: no workspace data is injected
    assert context == ""
