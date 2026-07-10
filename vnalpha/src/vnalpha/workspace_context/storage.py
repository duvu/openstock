from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from vnalpha.workspace_context.models import WorkspaceState

DEFAULT_WORKSPACE_ROOT = Path(".vnalpha") / "workspaces"
LATEST_POINTER_NAME = "latest.json"
INDEX_NAME = "index.json"
WORKSPACE_JSON_NAME = "workspace.json"
EVENTS_JSONL_NAME = "events.jsonl"
CONTEXT_MD_NAME = "context.md"
COMPACT_MD_NAME = "compact.md"
LOCK_NAME = ".lock"


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    workspace_id: str
    workspace_dir: Path
    workspace_json_path: Path
    context_path: Path
    compact_path: Path
    events_path: Path
    artifacts_dir: Path
    exports_dir: Path
    lock_path: Path


def resolve_workspace_root(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    env_override = os.environ.get("VNALPHA_WORKSPACE_ROOT", "").strip()
    if env_override:
        return Path(env_override)
    return DEFAULT_WORKSPACE_ROOT


def ensure_workspace_layout(
    *, root: Path | None = None, workspace_id: str
) -> WorkspacePaths:
    resolved_root = resolve_workspace_root(root)
    workspace_dir = resolved_root / workspace_id
    artifacts_dir = workspace_dir / "artifacts"
    exports_dir = workspace_dir / "exports"

    resolved_root.mkdir(parents=True, exist_ok=True)
    (resolved_root / "archive").mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)
    events_path = workspace_dir / EVENTS_JSONL_NAME
    events_path.touch(exist_ok=True)

    return WorkspacePaths(
        root=resolved_root,
        workspace_id=workspace_id,
        workspace_dir=workspace_dir,
        workspace_json_path=workspace_dir / WORKSPACE_JSON_NAME,
        context_path=workspace_dir / CONTEXT_MD_NAME,
        compact_path=workspace_dir / COMPACT_MD_NAME,
        events_path=events_path,
        artifacts_dir=artifacts_dir,
        exports_dir=exports_dir,
        lock_path=workspace_dir / LOCK_NAME,
    )


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _index_path(root: Path | None = None) -> Path:
    return resolve_workspace_root(root) / INDEX_NAME


def _write_workspace_index(
    *, root: Path | None = None, workspace_ids: list[str]
) -> Path:
    index_path = _index_path(root)
    payload = {
        "workspace_ids": sorted(workspace_ids),
        "count": len(workspace_ids),
    }
    _atomic_write_text(index_path, json.dumps(payload, indent=2, sort_keys=True))
    return index_path


def load_workspace_index(*, root: Path | None = None) -> dict[str, Any]:
    index_path = _index_path(root)
    if not index_path.exists():
        return {"workspace_ids": [], "count": 0}
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    workspace_ids = payload.get("workspace_ids", [])
    return {
        "workspace_ids": list(workspace_ids),
        "count": int(payload.get("count", len(workspace_ids))),
    }


def acquire_workspace_lock(*, root: Path | None = None, workspace_id: str) -> Path:
    paths = ensure_workspace_layout(root=root, workspace_id=workspace_id)
    _atomic_write_text(paths.lock_path, workspace_id)
    return paths.lock_path


def release_workspace_lock(*, root: Path | None = None, workspace_id: str) -> None:
    paths = ensure_workspace_layout(root=root, workspace_id=workspace_id)
    if paths.lock_path.exists():
        paths.lock_path.unlink()


def save_workspace_state(*, root: Path | None = None, state: WorkspaceState) -> Path:
    paths = ensure_workspace_layout(root=root, workspace_id=state.workspace_id)
    _atomic_write_text(
        paths.workspace_json_path,
        json.dumps(state.to_dict(), indent=2, sort_keys=True),
    )
    from vnalpha.workspace_context.integration import render_context_markdown

    _atomic_write_text(paths.context_path, render_context_markdown(state))
    existing_index = load_workspace_index(root=paths.root)
    workspace_ids = set(existing_index["workspace_ids"])
    workspace_ids.add(state.workspace_id)
    _write_workspace_index(root=paths.root, workspace_ids=sorted(workspace_ids))
    return paths.workspace_json_path


def load_workspace_state(
    *, root: Path | None = None, workspace_id: str
) -> WorkspaceState:
    paths = ensure_workspace_layout(root=root, workspace_id=workspace_id)
    payload = json.loads(paths.workspace_json_path.read_text(encoding="utf-8"))
    return WorkspaceState.from_dict(payload)


def save_latest_workspace_id(*, root: Path | None = None, workspace_id: str) -> Path:
    resolved_root = resolve_workspace_root(root)
    resolved_root.mkdir(parents=True, exist_ok=True)
    latest_path = resolved_root / LATEST_POINTER_NAME
    _atomic_write_text(
        latest_path,
        json.dumps({"workspace_id": workspace_id}, indent=2, sort_keys=True),
    )
    return latest_path


def load_latest_workspace_id(*, root: Path | None = None) -> str | None:
    latest_path = resolve_workspace_root(root) / LATEST_POINTER_NAME
    if not latest_path.exists():
        return None
    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    workspace_id = payload.get("workspace_id")
    return workspace_id if isinstance(workspace_id, str) else None


def append_workspace_event(
    *, root: Path | None = None, workspace_id: str, event: dict[str, Any]
) -> Path:
    paths = ensure_workspace_layout(root=root, workspace_id=workspace_id)
    with paths.events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True))
        handle.write("\n")
    return paths.events_path
