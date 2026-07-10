from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch

import vnalpha.workspace_context.cleaning as cleaning_module
from vnalpha.workspace_context.cleaning import clean_workspace
from vnalpha.workspace_context.lifecycle import (
    create_workspace,
    record_artifact,
    record_warning,
)
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
    assert "archive/artifacts/stale.tmp" in result.archived
    assert "artifacts/stale.tmp" in result.removed
    assert (archive_root / "events.old.jsonl").exists()
    assert (archive_root / "artifacts" / "stale.tmp").exists()
    assert not (workspace_dir / "events.old.jsonl").exists()
    assert not (workspace_dir / "artifacts" / "stale.tmp").exists()


def test_clean_workspace_defaults_to_dry_run_without_archiving(tmp_path) -> None:
    workspace = create_workspace(title="FPT workflow", mode="research", root=tmp_path)
    workspace_dir = tmp_path / workspace.workspace_id
    _write(workspace_dir / "artifacts" / "stale.tmp", "old")

    result = clean_workspace(workspace.workspace_id, root=tmp_path)

    assert result.dry_run is True
    assert result.archived == []
    assert result.removed == []
    assert (workspace_dir / "artifacts" / "stale.tmp").exists()
    assert not (
        tmp_path / "archive" / workspace.workspace_id / "artifacts" / "stale.tmp"
    ).exists()


def test_clean_workspace_cleans_only_explicitly_resolved_error_artifacts(
    tmp_path,
) -> None:
    workspace = create_workspace(title="HPG workflow", mode="research", root=tmp_path)
    workspace_dir = tmp_path / workspace.workspace_id
    resolved_path = "artifacts/resolved-error.json"
    unresolved_path = "artifacts/unresolved-error.json"
    record_artifact(
        workspace,
        WorkspaceArtifactRef(
            artifact_id="error-1",
            artifact_type="error",
            path=resolved_path,
            summary="Resolved price feed error",
            created_at="2026-07-10T01:00:00+00:00",
            metadata={"status": "resolved"},
        ),
        root=tmp_path,
    )
    record_artifact(
        workspace,
        WorkspaceArtifactRef(
            artifact_id="error-2",
            artifact_type="error",
            path=unresolved_path,
            summary="Unresolved market data error",
            created_at="2026-07-10T01:00:00+00:00",
            metadata={"status": "open"},
        ),
        root=tmp_path,
    )
    _write(workspace_dir / resolved_path, "resolved")
    _write(workspace_dir / unresolved_path, "unresolved")

    result = clean_workspace(
        workspace.workspace_id, root=tmp_path, resolved_errors=True
    )

    assert result.dry_run is True
    assert result.plan is not None
    assert resolved_path in result.plan.remove
    assert unresolved_path in result.plan.keep
    assert (workspace_dir / resolved_path).exists()
    assert (workspace_dir / unresolved_path).exists()


def test_clean_workspace_emits_events_for_destructive_cleanup(
    tmp_path, monkeypatch: MonkeyPatch
) -> None:
    workspace = create_workspace(title="VIC workflow", mode="research", root=tmp_path)
    workspace_dir = tmp_path / workspace.workspace_id
    audit_events: list[tuple[str, str, str, dict[str, str | int | float | bool]]] = []
    _write(workspace_dir / "artifacts" / "stale.tmp", "old")

    def record_audit_event(
        *,
        event_type: str,
        workspace_id: str,
        summary: str,
        metadata: dict[str, str | int | float | bool],
    ) -> None:
        audit_events.append((event_type, workspace_id, summary, metadata))

    monkeypatch.setattr(
        cleaning_module, "emit_workspace_audit_event", record_audit_event
    )

    clean_workspace(workspace.workspace_id, root=tmp_path, dry_run=False)

    events = [
        json.loads(line)
        for line in (workspace_dir / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert any(event["event_type"] == "WORKSPACE_CLEANED" for event in events)
    assert len(audit_events) == 1
    event_type, event_workspace_id, summary, metadata = audit_events[0]
    assert event_type == "WORKSPACE_CLEANED"
    assert event_workspace_id == workspace.workspace_id
    assert summary == "Workspace cleaned"
    assert set(metadata) == {"archived_count", "dry_run", "removed_count"}
    assert metadata["dry_run"] is False
