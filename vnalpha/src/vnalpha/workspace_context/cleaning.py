from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from vnalpha.workspace_context.models import CleanPlan, CleanResult
from vnalpha.workspace_context.storage import ensure_workspace_layout, load_workspace_state, resolve_workspace_root


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _rel(path: Path, workspace_dir: Path) -> str:
    return path.relative_to(workspace_dir).as_posix()


def _protected_paths(workspace_dir: Path, pinned_artifacts: set[str]) -> tuple[set[str], set[str]]:
    keep = {
        "workspace.json",
        "events.jsonl",
        "compact.md",
        "context.md",
    }
    protected = {"audit.jsonl"}
    keep.update(pinned_artifacts)
    return keep, protected


def _classify_workspace(workspace_dir: Path, pinned_artifacts: set[str]) -> CleanPlan:
    keep, protected = _protected_paths(workspace_dir, pinned_artifacts)
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
        if rel_path.startswith("artifacts/") and rel_path not in pinned_artifacts:
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


def clean_workspace(workspace_id: str, *, root: Path | None = None, dry_run: bool = True) -> CleanResult:
    resolved_root = resolve_workspace_root(root)
    paths = ensure_workspace_layout(root=resolved_root, workspace_id=workspace_id)
    state = load_workspace_state(root=resolved_root, workspace_id=workspace_id)
    pinned_artifacts = {
        artifact.path for artifact in state.active_artifacts if artifact.pinned and artifact.path
    }
    plan = _classify_workspace(paths.workspace_dir, pinned_artifacts)
    if dry_run:
        return CleanResult(
            workspace_id=workspace_id,
            dry_run=True,
            kept=plan.keep,
            warnings=[],
            generated_at=_now_iso(),
            plan=plan,
        )

    archive_root = resolved_root / "archive" / workspace_id
    archive_root.mkdir(parents=True, exist_ok=True)
    archived: list[str] = []
    removed: list[str] = []

    for rel_path in plan.archive:
        source = paths.workspace_dir / rel_path
        target = archive_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        source.unlink()
        archived.append(f"archive/{rel_path}")

    for rel_path in plan.remove:
        source = paths.workspace_dir / rel_path
        if source.exists():
            source.unlink()
            removed.append(rel_path)

    return CleanResult(
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
