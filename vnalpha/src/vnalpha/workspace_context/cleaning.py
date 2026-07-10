from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from vnalpha.workspace_context.models import CleanPlan, CleanResult
from vnalpha.workspace_context.observability import emit_workspace_audit_event
from vnalpha.workspace_context.storage import (
    append_workspace_event,
    ensure_workspace_layout,
    load_workspace_state,
    resolve_workspace_root,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _rel(path: Path, workspace_dir: Path) -> str:
    return path.relative_to(workspace_dir).as_posix()


def _protected_paths(active_artifacts: set[str]) -> tuple[set[str], set[str]]:
    keep = {
        "workspace.json",
        "events.jsonl",
        "compact.md",
        "context.md",
    }
    protected = {"audit.jsonl"}
    keep.update(active_artifacts)
    return keep, protected


def _classify_workspace(workspace_dir: Path, active_artifacts: set[str]) -> CleanPlan:
    keep, protected = _protected_paths(active_artifacts)
    archive: list[str] = []
    remove: list[str] = []
    needs_confirmation: list[str] = []

    for path in sorted(workspace_dir.rglob("*")):
        if path.is_dir():
            continue
        rel_path = _rel(path, workspace_dir)
        if rel_path in keep:
            continue
        if rel_path in protected:
            continue
        if rel_path.startswith("notes/"):
            needs_confirmation.append(rel_path)
            continue
        if rel_path.startswith("artifacts/"):
            remove.append(rel_path)
            continue
        if rel_path.endswith(".old.jsonl"):
            archive.append(rel_path)
            continue

    summary = (
        f"keep={len(keep)} protected={len(protected)} "
        f"archive={len(archive)} remove={len(remove)} confirm={len(needs_confirmation)}"
    )
    return CleanPlan(
        workspace_id=workspace_dir.name,
        dry_run=True,
        archive_first=True,
        keep=sorted(keep),
        archive=archive,
        remove=remove,
        needs_confirmation=needs_confirmation,
        protected=sorted(protected),
        summary=summary,
    )


def clean_workspace(
    workspace_id: str,
    *,
    root: Path | None = None,
    dry_run: bool = True,
    resolved_errors: bool = False,
) -> CleanResult:
    resolved_root = resolve_workspace_root(root)
    paths = ensure_workspace_layout(root=resolved_root, workspace_id=workspace_id)
    state = load_workspace_state(root=resolved_root, workspace_id=workspace_id)
    active_artifacts = {
        artifact.path for artifact in state.active_artifacts if artifact.path
    }
    resolved_error_artifacts = {
        artifact.path
        for artifact in state.active_artifacts
        if (
            artifact.artifact_type == "error"
            and artifact.metadata.get("status") == "resolved"
            and artifact.path
        )
    }
    protected_artifacts = (
        active_artifacts - resolved_error_artifacts
        if resolved_errors
        else active_artifacts
    )
    plan = _classify_workspace(paths.workspace_dir, protected_artifacts)
    if dry_run:
        result = CleanResult(
            workspace_id=workspace_id,
            dry_run=True,
            kept=plan.keep,
            warnings=[],
            generated_at=_now_iso(),
            plan=plan,
        )
        append_workspace_event(
            root=resolved_root,
            workspace_id=workspace_id,
            event={
                "event_id": f"evt-{result.generated_at}",
                "event_type": "WORKSPACE_CLEAN_DRY_RUN",
                "workspace_id": workspace_id,
                "created_at": result.generated_at,
                "metadata": {
                    "archive_count": len(plan.archive),
                    "remove_count": len(plan.remove),
                },
            },
        )
        emit_workspace_audit_event(
            event_type="WORKSPACE_CLEAN_DRY_RUN",
            workspace_id=workspace_id,
            summary="Workspace clean dry run",
            metadata={
                "archive_count": len(plan.archive),
                "remove_count": len(plan.remove),
            },
        )
        return result

    archive_root = resolved_root / "archive" / workspace_id
    archive_root.mkdir(parents=True, exist_ok=True)
    archived: list[str] = []
    removed: list[str] = []

    for rel_path in [*plan.archive, *plan.remove]:
        source = paths.workspace_dir / rel_path
        target = archive_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        source.unlink()
        archived.append(f"archive/{rel_path}")
        if rel_path in plan.remove:
            removed.append(rel_path)

    result = CleanResult(
        workspace_id=workspace_id,
        dry_run=False,
        archived=archived,
        removed=removed,
        kept=plan.keep,
        warnings=[],
        generated_at=_now_iso(),
        plan=CleanPlan(
            workspace_id=plan.workspace_id,
            dry_run=False,
            archive_first=plan.archive_first,
            keep=plan.keep,
            archive=plan.archive,
            remove=plan.remove,
            needs_confirmation=plan.needs_confirmation,
            protected=plan.protected,
            summary=plan.summary,
        ),
    )
    append_workspace_event(
        root=resolved_root,
        workspace_id=workspace_id,
        event={
            "event_id": f"evt-{result.generated_at}",
            "event_type": "WORKSPACE_CLEANED",
            "workspace_id": workspace_id,
            "created_at": result.generated_at,
            "metadata": {
                "archived_count": len(archived),
                "removed_count": len(removed),
            },
        },
    )
    emit_workspace_audit_event(
        event_type="WORKSPACE_CLEANED",
        workspace_id=workspace_id,
        summary="Workspace cleaned",
        metadata={
            "archived_count": len(archived),
            "dry_run": False,
            "removed_count": len(removed),
        },
    )
    return result
