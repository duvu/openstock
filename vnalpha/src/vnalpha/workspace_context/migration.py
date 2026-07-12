from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from vnalpha.workspace_context.models import WorkspaceState
from vnalpha.workspace_context.storage import (
    _atomic_write_text,
    load_latest_workspace_id,
    load_workspace_index,
    load_workspace_state,
    resolve_workspace_root,
    save_latest_workspace_id,
    save_workspace_state,
)


class WorkspaceMigrationConflictError(Exception):
    def __init__(self, roots: tuple[str, ...]) -> None:
        self.roots = roots
        super().__init__()

    def __str__(self) -> str:
        return "Multiple workspace roots require an explicit source: " + ", ".join(
            self.roots
        )


class LegacyWorkspaceNotFoundError(Exception):
    def __init__(self, searched_from: str) -> None:
        self.searched_from = searched_from
        super().__init__()

    def __str__(self) -> str:
        return f"No legacy workspace root found from {self.searched_from}."


@dataclass(frozen=True, slots=True)
class WorkspaceMigrationResult:
    source_root: str
    destination_root: str
    backup_root: str
    workspace_ids: tuple[str, ...]
    active_workspace_id: str | None
    checksums: dict[str, str]


def _is_active_workspace(root: Path) -> bool:
    latest_id = load_latest_workspace_id(root=root)
    if latest_id is None:
        return False
    try:
        return (
            load_workspace_state(root=root, workspace_id=latest_id).status == "active"
        )
    except (FileNotFoundError, KeyError, TypeError, json.JSONDecodeError):
        return False


def detect_legacy_workspace_roots(
    *, canonical_root: Path | None = None, cwd: Path | None = None
) -> tuple[Path, ...]:
    destination = resolve_workspace_root(canonical_root)
    if _is_active_workspace(destination):
        return ()
    base = (cwd or Path.cwd()).expanduser().resolve()
    candidates: set[Path] = set()
    for ancestor in (base, *base.parents):
        candidates.add(ancestor / ".vnalpha" / "workspaces")
        candidates.add(ancestor / "vnalpha" / ".vnalpha" / "workspaces")
    canonical = destination.resolve()
    return tuple(
        sorted(
            (
                candidate.resolve()
                for candidate in candidates
                if candidate.is_dir() and candidate.resolve() != canonical
            ),
            key=str,
        )
    )


def _workspace_ids(root: Path) -> tuple[str, ...]:
    indexed = load_workspace_index(root=root).get("workspace_ids", [])
    candidates = {
        workspace_id for workspace_id in indexed if isinstance(workspace_id, str)
    }
    if root.is_dir():
        candidates.update(
            child.name
            for child in root.iterdir()
            if child.is_dir() and (child / "workspace.json").is_file()
        )
    return tuple(
        sorted(
            workspace_id
            for workspace_id in candidates
            if (root / workspace_id / "workspace.json").is_file()
        )
    )


def _sha256_files(root: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            checksums[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return checksums


def migrate_legacy_workspaces(
    *,
    source_root: Path | None = None,
    destination_root: Path,
    cwd: Path | None = None,
) -> WorkspaceMigrationResult:
    destination = destination_root.expanduser().resolve()
    if source_root is None:
        roots = detect_legacy_workspace_roots(
            canonical_root=destination,
            cwd=cwd,
        )
        if len(roots) > 1:
            raise WorkspaceMigrationConflictError(tuple(map(str, roots)))
        if not roots:
            raise LegacyWorkspaceNotFoundError(str((cwd or Path.cwd()).resolve()))
        source = roots[0]
    else:
        source = source_root.expanduser().resolve()
        if not source.is_dir():
            raise LegacyWorkspaceNotFoundError(str(source))
    if source == destination:
        raise WorkspaceMigrationConflictError((str(source),))
    existing_ids = _workspace_ids(destination) if destination.exists() else ()
    if existing_ids:
        marker = destination / "migration.json"
        try:
            marker_payload = json.loads(marker.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            marker_payload = None
        if (
            isinstance(marker_payload, dict)
            and marker_payload.get("source_root") == str(source)
            and tuple(marker_payload.get("workspace_ids", ())) == existing_ids
        ):
            backup_relative = Path(str(marker_payload["backup_root"]))
            backup = destination / backup_relative
            return WorkspaceMigrationResult(
                source_root=str(source),
                destination_root=str(destination),
                backup_root=backup_relative.as_posix(),
                workspace_ids=existing_ids,
                active_workspace_id=load_latest_workspace_id(root=destination),
                checksums=_sha256_files(backup),
            )
        raise WorkspaceMigrationConflictError((str(destination),))
    if any(path.is_symlink() for path in source.rglob("*")):
        raise WorkspaceMigrationConflictError((str(source),))

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + f"-{uuid4().hex[:8]}"
    backup_relative = Path("archive") / "legacy-migration" / stamp
    backup = destination / backup_relative
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, backup, symlinks=False)

    workspace_ids = _workspace_ids(source)
    if not workspace_ids:
        raise LegacyWorkspaceNotFoundError(str(source))
    for workspace_id in workspace_ids:
        state: WorkspaceState = load_workspace_state(
            root=source, workspace_id=workspace_id
        )
        save_workspace_state(root=destination, state=state)
        source_workspace = source / workspace_id
        destination_workspace = destination / workspace_id
        for directory_name in ("artifacts", "exports"):
            source_directory = source_workspace / directory_name
            destination_directory = destination_workspace / directory_name
            if source_directory.is_dir():
                shutil.copytree(
                    source_directory,
                    destination_directory,
                    dirs_exist_ok=True,
                    symlinks=False,
                )

    source_latest = load_latest_workspace_id(root=source)
    active_workspace_id: str | None = None
    if source_latest in workspace_ids:
        active_state = load_workspace_state(root=source, workspace_id=source_latest)
        if active_state.status == "active":
            save_latest_workspace_id(root=destination, workspace_id=source_latest)
            active_workspace_id = source_latest

    _atomic_write_text(
        destination / "migration.json",
        json.dumps(
            {
                "source_root": str(source),
                "backup_root": backup_relative.as_posix(),
                "workspace_ids": list(workspace_ids),
            },
            indent=2,
            sort_keys=True,
        ),
    )

    return WorkspaceMigrationResult(
        source_root=str(source),
        destination_root=str(destination),
        backup_root=backup_relative.as_posix(),
        workspace_ids=workspace_ids,
        active_workspace_id=active_workspace_id,
        checksums=_sha256_files(backup),
    )
