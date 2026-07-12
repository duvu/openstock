from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import mkdtemp
from uuid import uuid4

from vnalpha.workspace_context.lifecycle import get_or_create_latest_workspace
from vnalpha.workspace_context.models import WorkspaceState, WorkspaceStatus
from vnalpha.workspace_context.storage import (
    clear_latest_workspace_id,
    ensure_workspace_layout,
    load_workspace_state,
    quarantine_latest_workspace_pointer,
    resolve_workspace_root,
    save_workspace_state,
)


@dataclass(frozen=True, slots=True)
class WorkspaceRecoveryResult:
    workspace: WorkspaceState
    warnings: tuple[str, ...] = ()
    quarantined_paths: tuple[str, ...] = ()
    temporary: bool = False


def recover_workspace(root: Path | None = None) -> WorkspaceRecoveryResult:
    """Load a workspace while quarantining malformed state and preserving startup."""

    resolved_root = resolve_workspace_root(root)
    quarantined: list[str] = []
    warnings: list[str] = []
    latest_pointer_quarantine = _quarantine_invalid_latest(resolved_root)
    if latest_pointer_quarantine is not None:
        quarantined.append(str(latest_pointer_quarantine))
        warnings.append("The latest workspace pointer was malformed and quarantined.")
    for workspace_dir in _workspace_directories(resolved_root):
        workspace_path = workspace_dir / "workspace.json"
        try:
            load_workspace_state(root=resolved_root, workspace_id=workspace_dir.name)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            quarantined_path = _quarantine_file(
                workspace_path, resolved_root / "archive" / "quarantine"
            )
            if quarantined_path is not None:
                quarantined.append(str(quarantined_path))
                warnings.append(
                    f"Workspace {workspace_dir.name} was malformed and quarantined."
                )
            if _latest_id(resolved_root) == workspace_dir.name:
                clear_latest_workspace_id(root=resolved_root)
    try:
        workspace = get_or_create_latest_workspace(root=resolved_root)
        return WorkspaceRecoveryResult(
            workspace=workspace,
            warnings=tuple(warnings),
            quarantined_paths=tuple(quarantined),
        )
    except (OSError, PermissionError, RuntimeError, ValueError) as exc:
        warnings.append(f"Canonical workspace unavailable: {type(exc).__name__}.")
        temporary = _temporary_workspace(resolved_root)
        return WorkspaceRecoveryResult(
            workspace=temporary,
            warnings=tuple(warnings),
            quarantined_paths=tuple(quarantined),
            temporary=True,
        )


def inspect_workspace(root: Path | None = None) -> tuple[str, ...]:
    """Return malformed latest/state paths without changing them."""

    resolved_root = resolve_workspace_root(root)
    invalid: list[str] = []
    latest = resolved_root / "latest.json"
    if latest.exists():
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not isinstance(
                payload.get("workspace_id"), str
            ):
                invalid.append(str(latest))
        except (OSError, json.JSONDecodeError):
            invalid.append(str(latest))
    for workspace_dir in _workspace_directories(resolved_root):
        try:
            load_workspace_state(root=resolved_root, workspace_id=workspace_dir.name)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            invalid.append(str(workspace_dir / "workspace.json"))
    return tuple(sorted(invalid))


def _workspace_directories(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    return tuple(
        sorted(
            child
            for child in root.iterdir()
            if child.is_dir() and child.name != "archive"
        )
    )


def _latest_id(root: Path) -> str | None:
    path = root / "latest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    value = payload.get("workspace_id") if isinstance(payload, dict) else None
    return value if isinstance(value, str) else None


def _quarantine_invalid_latest(root: Path) -> Path | None:
    path = root / "latest.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("workspace_id"), str):
            return None
    except (OSError, json.JSONDecodeError):
        pass
    return quarantine_latest_workspace_pointer(root=root)


def _quarantine_file(path: Path, destination: Path) -> Path | None:
    if not path.exists():
        return None
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = destination / f"{path.parent.name}-{stamp}-{uuid4().hex[:8]}{path.suffix}"
    path.replace(target)
    return target


def _temporary_workspace(root: Path) -> WorkspaceState:
    workspace_id = f"ws-temporary-{uuid4().hex[:10]}"
    now = datetime.now(UTC).isoformat()
    state = WorkspaceState(
        workspace_id=workspace_id,
        title="Temporary recovery workspace",
        status=WorkspaceStatus.TEMPORARY.value,
        mode="recovery",
        created_at=now,
        updated_at=now,
        context_size={"events": 0, "inputs": 0, "artifacts": 0},
    )
    try:
        ensure_workspace_layout(root=root, workspace_id=workspace_id)
        save_workspace_state(root=root, state=state)
    except OSError:
        fallback_root = Path(mkdtemp(prefix="openstock-workspace-"))
        ensure_workspace_layout(root=fallback_root, workspace_id=workspace_id)
        save_workspace_state(root=fallback_root, state=state)
    return state
