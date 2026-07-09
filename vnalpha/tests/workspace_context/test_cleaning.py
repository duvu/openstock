from __future__ import annotations

from pathlib import Path

from vnalpha.workspace_context.cleaning import clean_workspace
from vnalpha.workspace_context.lifecycle import create_workspace, record_artifact, record_warning
from vnalpha.workspace_context.models import WorkspaceArtifactRef


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_clean_workspace_dry_run_classifies_files_safely(tmp_path) -> None:
    workspace = create_workspace(title="FPT workflow", mode="research", root=tmp_path)
    record_warning(workspace, "stale compact", root=tmp_path)
    record_artifact(
        workspace,
        WorkspaceArtifactRef(
            artifact_id="watchlist-1",
            artifact_type="watchlist",
            path="artifacts/watchlist.json",
            summary="Pinned watchlist snapshot",
            created_at="2026-07-09T02:10:00+00:00",
            source_refs=["artifact:watchlist-1"],
            pinned=True,
        ),
        root=tmp_path,
    )

    workspace_dir = tmp_path / workspace.workspace_id
    _write(workspace_dir / "artifacts" / "stale.tmp", "old")
    _write(workspace_dir / "notes" / "private.md", "user-authored")
    _write(workspace_dir / "audit.jsonl", "immutable audit")
    _write(workspace_dir / "compact.md", "existing compact")

    result = clean_workspace(workspace.workspace_id, root=tmp_path, dry_run=True)

    assert result.dry_run is True
    assert result.plan is not None
    assert "workspace.json" in result.plan.keep
    assert "compact.md" in result.plan.keep
    assert "audit.jsonl" in result.plan.protected
    assert "artifacts/watchlist.json" in result.plan.keep
    assert "artifacts/stale.tmp" in result.plan.remove
    assert "notes/private.md" in result.plan.needs_confirmation
    assert (workspace_dir / "artifacts" / "stale.tmp").exists()


def test_clean_workspace_archive_first_executes_removal(tmp_path) -> None:
    workspace = create_workspace(title="HPG workflow", mode="research", root=tmp_path)
    workspace_dir = tmp_path / workspace.workspace_id

    _write(workspace_dir / "artifacts" / "stale.tmp", "old")
    _write(workspace_dir / "events.old.jsonl", "old events")

    result = clean_workspace(workspace.workspace_id, root=tmp_path, dry_run=False)

    archive_root = tmp_path / "archive" / workspace.workspace_id
    assert result.dry_run is False
    assert result.plan is not None
    assert "archive/events.old.jsonl" in result.archived
    assert "artifacts/stale.tmp" in result.removed
    assert (archive_root / "events.old.jsonl").exists()
    assert not (workspace_dir / "events.old.jsonl").exists()
    assert not (workspace_dir / "artifacts" / "stale.tmp").exists()
