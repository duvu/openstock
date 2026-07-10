from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch

from vnalpha.workspace_context import export as export_module
from vnalpha.workspace_context.models import WorkspaceArtifactRef, WorkspaceState
from vnalpha.workspace_context.observability import WorkspaceAuditMetadata
from vnalpha.workspace_context.storage import save_workspace_state


def test_export_workspace_bundles_only_pinned_workspace_artifacts(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Given: a workspace with approved, unapproved, and external artifact references.
    workspace_id = "ws-20260710-001"
    state = WorkspaceState(
        workspace_id=workspace_id,
        title="Exportable workspace",
        status="active",
        mode="research",
        created_at="2026-07-10T01:00:00+00:00",
        updated_at="2026-07-10T02:00:00+00:00",
        active_artifacts=[
            WorkspaceArtifactRef(
                artifact_id="approved",
                artifact_type="report",
                path="artifacts/approved.md",
                summary="Approved report",
                created_at="2026-07-10T01:30:00+00:00",
                pinned=True,
            ),
            WorkspaceArtifactRef(
                artifact_id="unapproved",
                artifact_type="report",
                path="artifacts/unapproved.md",
                summary="Unapproved report",
                created_at="2026-07-10T01:30:00+00:00",
            ),
            WorkspaceArtifactRef(
                artifact_id="external",
                artifact_type="audit",
                path=str(tmp_path / "external-audit.jsonl"),
                summary="External audit",
                created_at="2026-07-10T01:30:00+00:00",
                pinned=True,
            ),
        ],
    )
    save_workspace_state(root=tmp_path, state=state)
    workspace_dir = tmp_path / workspace_id
    (workspace_dir / "compact.md").write_text("Compact context", encoding="utf-8")
    (workspace_dir / "artifacts" / "approved.md").write_text(
        "Approved", encoding="utf-8"
    )
    (workspace_dir / "artifacts" / "unapproved.md").write_text(
        "Unapproved", encoding="utf-8"
    )
    (workspace_dir / "events.jsonl").write_text(
        '{"event_type":"sensitive"}\n', encoding="utf-8"
    )
    (workspace_dir / "audit.jsonl").write_text("sensitive audit", encoding="utf-8")
    (tmp_path / "external-audit.jsonl").write_text("external audit", encoding="utf-8")
    audit_events: list[WorkspaceAuditMetadata] = []

    def capture_audit_event(
        *,
        event_type: str,
        workspace_id: str,
        summary: str,
        metadata: WorkspaceAuditMetadata,
    ) -> None:
        audit_events.append(
            {
                "event_type": event_type,
                "workspace_id": workspace_id,
                "summary": summary,
                **metadata,
            }
        )

    monkeypatch.setattr(
        export_module,
        "emit_workspace_audit_event",
        capture_audit_event,
    )

    # When: the workspace is exported.
    result = export_module.export_workspace(workspace_id, root=tmp_path)

    # Then: only policy-approved workspace content and its manifest are bundled.
    bundle_dir = Path(result.bundle_dir)
    assert sorted(result.exported_files) == [
        "artifacts/approved.md",
        "compact.md",
        "context.md",
        "workspace.json",
    ]
    assert (bundle_dir / "artifacts" / "approved.md").read_text(
        encoding="utf-8"
    ) == "Approved"
    assert not (bundle_dir / "artifacts" / "unapproved.md").exists()
    assert not (bundle_dir / "events.jsonl").exists()
    assert not (bundle_dir / "audit.jsonl").exists()
    assert not (bundle_dir / "external-audit.jsonl").exists()

    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["workspace_id"] == workspace_id
    assert manifest["source_path"] == str(workspace_dir)
    assert manifest["files"] == result.exported_files
    assert manifest["checksums"] == result.checksums
    assert manifest["generated_at"] == result.generated_at
    events = [
        json.loads(line)
        for line in (workspace_dir / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert events[-1]["event_type"] == "WORKSPACE_EXPORTED"
    assert audit_events == [
        {
            "event_type": "WORKSPACE_EXPORTED",
            "workspace_id": workspace_id,
            "summary": "Workspace exported",
            "exported_count": 4,
        }
    ]
