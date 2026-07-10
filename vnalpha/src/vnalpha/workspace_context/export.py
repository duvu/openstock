from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from vnalpha.workspace_context.models import ExportResult, WorkspaceState
from vnalpha.workspace_context.observability import emit_workspace_audit_event
from vnalpha.workspace_context.storage import (
    _atomic_write_text,
    append_workspace_event,
    ensure_workspace_layout,
    load_workspace_state,
    resolve_workspace_root,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _bundle_name(generated_at: str) -> str:
    return generated_at.replace("+00:00", "Z").replace(":", "").replace(".", "-")


def _approved_artifact_paths(state: WorkspaceState, workspace_dir: Path) -> list[Path]:
    approved: list[Path] = []
    for artifact in state.active_artifacts:
        if not artifact.pinned:
            continue
        relative_path = PurePosixPath(artifact.path)
        if (
            relative_path.is_absolute()
            or not relative_path.parts
            or relative_path.parts[0] != "artifacts"
            or ".." in relative_path.parts
        ):
            continue
        source_path = workspace_dir.joinpath(*relative_path.parts)
        if source_path.is_symlink() or not source_path.is_file():
            continue
        approved.append(source_path)
    return approved


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_workspace(workspace_id: str, *, root: Path | None = None) -> ExportResult:
    resolved_root = resolve_workspace_root(root)
    paths = ensure_workspace_layout(root=resolved_root, workspace_id=workspace_id)
    state = load_workspace_state(root=resolved_root, workspace_id=workspace_id)
    generated_at = _now_iso()
    bundle_dir = paths.exports_dir / _bundle_name(generated_at)
    bundle_dir.mkdir(parents=True, exist_ok=False)

    sources = [paths.workspace_json_path, paths.context_path]
    if paths.compact_path.is_file():
        sources.append(paths.compact_path)
    sources.extend(_approved_artifact_paths(state, paths.workspace_dir))

    exported_files: list[str] = []
    checksums: dict[str, str] = {}
    for source_path in sources:
        relative_path = source_path.relative_to(paths.workspace_dir)
        relative_name = relative_path.as_posix()
        target_path = bundle_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        exported_files.append(relative_name)
        checksums[relative_name] = _checksum(target_path)

    manifest_path = bundle_dir / "manifest.json"
    _atomic_write_text(
        manifest_path,
        json.dumps(
            {
                "workspace_id": workspace_id,
                "generated_at": generated_at,
                "source_path": str(paths.workspace_dir),
                "files": exported_files,
                "checksums": checksums,
            },
            indent=2,
            sort_keys=True,
        ),
    )
    append_workspace_event(
        root=resolved_root,
        workspace_id=workspace_id,
        event={
            "event_id": f"evt-{generated_at}",
            "event_type": "WORKSPACE_EXPORTED",
            "workspace_id": workspace_id,
            "created_at": generated_at,
            "metadata": {"exported_count": len(exported_files)},
        },
    )
    emit_workspace_audit_event(
        event_type="WORKSPACE_EXPORTED",
        workspace_id=workspace_id,
        summary="Workspace exported",
        metadata={"exported_count": len(exported_files)},
    )
    return ExportResult(
        workspace_id=workspace_id,
        bundle_dir=str(bundle_dir),
        manifest_path=str(manifest_path),
        exported_files=exported_files,
        checksums=checksums,
        generated_at=generated_at,
    )
