from __future__ import annotations

from vnalpha.workspace_context.compaction import compact_workspace
from vnalpha.workspace_context.lifecycle import (
    create_workspace,
    record_artifact,
    record_input,
    record_warning,
    resume_workspace,
)
from vnalpha.workspace_context.models import WorkspaceArtifactRef


def test_compact_workspace_writes_compact_file_and_updates_state(tmp_path) -> None:
    workspace = create_workspace(title="FPT workflow", mode="research", root=tmp_path)
    record_input(workspace, "Compare FPT and HPG", "user", root=tmp_path)
    record_warning(workspace, "compact recommended", root=tmp_path)
    record_artifact(
        workspace,
        WorkspaceArtifactRef(
            artifact_id="watchlist-1",
            artifact_type="watchlist",
            path="artifacts/watchlist.json",
            summary="Daily shortlist",
            created_at="2026-07-09T01:10:00+00:00",
            source_refs=["candidate_score:FPT:2026-07-09"],
        ),
        root=tmp_path,
    )

    result = compact_workspace(workspace.workspace_id, root=tmp_path)
    updated = resume_workspace(workspace.workspace_id, root=tmp_path)
    compact_text = (tmp_path / workspace.workspace_id / "compact.md").read_text(
        encoding="utf-8"
    )

    assert result.workspace_id == workspace.workspace_id
    assert result.compact_path == "compact.md"
    assert result.before_size["events"] >= 1
    assert result.after_size["summary_lines"] >= 1
    assert "active_symbols" in result.preserved_items
    assert updated.last_compacted_at is not None
    assert "# Compact Workspace Summary" in compact_text
    assert "Daily shortlist" in compact_text
    assert "compact recommended" in compact_text
