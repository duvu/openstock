from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from vnalpha.observability.redaction import redact_str
from vnalpha.workspace_context.models import JsonDict, WorkspaceState
from vnalpha.workspace_context.storage import (
    _atomic_write_text,
    ensure_workspace_layout,
)


@dataclass(frozen=True, slots=True)
class WorkspaceLimits:
    max_inputs: int = 200
    max_warnings: int = 100
    max_errors: int = 100
    max_active_artifacts: int = 100
    max_done_tasks: int = 100
    max_events: int = 1000


@dataclass(frozen=True, slots=True)
class RetentionResult:
    state: WorkspaceState
    archived_counts: dict[str, int]


def _env_limit(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return max(int(raw), 1)
    except ValueError:
        return default


def workspace_limits() -> WorkspaceLimits:
    return WorkspaceLimits(
        max_inputs=_env_limit("VNALPHA_WORKSPACE_MAX_INPUTS", 200),
        max_warnings=_env_limit("VNALPHA_WORKSPACE_MAX_WARNINGS", 100),
        max_errors=_env_limit("VNALPHA_WORKSPACE_MAX_ERRORS", 100),
        max_active_artifacts=_env_limit("VNALPHA_WORKSPACE_MAX_ACTIVE_ARTIFACTS", 100),
        max_done_tasks=_env_limit("VNALPHA_WORKSPACE_MAX_DONE_TASKS", 100),
        max_events=_env_limit("VNALPHA_WORKSPACE_MAX_EVENTS", 1000),
    )


def _append_archive(path: Path, values: list[JsonDict]) -> None:
    if not values:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True))
            handle.write("\n")
    _atomic_write_text(
        path.with_name(f"{path.name}.sha256"),
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n",
    )


def _trim_recent_inputs(
    state: WorkspaceState,
    workspace_dir: Path,
    limit: int,
    archived_counts: dict[str, int],
) -> list[JsonDict]:
    if len(state.recent_inputs) <= limit:
        return [item.to_dict() for item in state.recent_inputs]
    archived = [item.to_dict() for item in state.recent_inputs[:-limit]]
    _append_archive(workspace_dir / "archive" / "inputs.jsonl", archived)
    archived_counts["inputs"] = len(archived)
    return [item.to_dict() for item in state.recent_inputs[-limit:]]


def _trim_messages(
    values: list[str],
    workspace_dir: Path,
    name: str,
    limit: int,
    archived_counts: dict[str, int],
) -> list[str]:
    redacted = [redact_str(value, mode="redacted") for value in values]
    if len(redacted) <= limit:
        return redacted
    archived = [{"text": value} for value in redacted[:-limit]]
    _append_archive(workspace_dir / "archive" / f"{name}.jsonl", archived)
    archived_counts[name] = len(archived)
    return redacted[-limit:]


def _trim_artifacts(
    state: WorkspaceState,
    workspace_dir: Path,
    limit: int,
    archived_counts: dict[str, int],
) -> list[JsonDict]:
    pinned = [artifact for artifact in state.active_artifacts if artifact.pinned]
    unpinned = [artifact for artifact in state.active_artifacts if not artifact.pinned]
    keep_count = max(limit - len(pinned), 0)
    retained = [*pinned, *(unpinned[-keep_count:] if keep_count else [])]
    retained_ids = {artifact.artifact_id for artifact in retained}
    archived = [
        artifact.to_dict()
        for artifact in state.active_artifacts
        if artifact.artifact_id not in retained_ids
    ]
    _append_archive(workspace_dir / "archive" / "artifacts.jsonl", archived)
    if archived:
        archived_counts["artifacts"] = len(archived)
    return [artifact.to_dict() for artifact in retained]


def _trim_tasks(
    state: WorkspaceState,
    workspace_dir: Path,
    limit: int,
    archived_counts: dict[str, int],
) -> list[JsonDict]:
    done = [task for task in state.open_tasks if task.status in {"completed", "done"}]
    pending = [
        task for task in state.open_tasks if task.status not in {"completed", "done"}
    ]
    archived = [{"task": task.to_dict()} for task in done[:-limit]]
    _append_archive(workspace_dir / "archive" / "tasks.jsonl", archived)
    if archived:
        archived_counts["tasks"] = len(archived)
    return [task.to_dict() for task in [*pending, *done[-limit:]]]


def _rotate_events(
    workspace_dir: Path,
    limit: int,
    archived_counts: dict[str, int],
) -> int:
    events_path = workspace_dir / "events.jsonl"
    if not events_path.exists():
        return 0
    lines = events_path.read_text(encoding="utf-8").splitlines()
    if len(lines) <= limit:
        return len(lines)
    archived_lines = lines[:-limit]
    archive_path = workspace_dir / "archive" / "events.jsonl"
    _append_archive(
        archive_path,
        [{"event": line} for line in archived_lines],
    )
    _atomic_write_text(events_path, "\n".join(lines[-limit:]) + "\n")
    archived_counts["events"] = len(archived_lines)
    return limit


def enforce_retention(
    *,
    root: Path,
    state: WorkspaceState,
    limits: WorkspaceLimits | None = None,
) -> RetentionResult:
    resolved_limits = limits or workspace_limits()
    paths = ensure_workspace_layout(root=root, workspace_id=state.workspace_id)
    archived_counts: dict[str, int] = {}
    context_size = dict(state.context_size)
    context_size["events"] = _rotate_events(
        paths.workspace_dir,
        resolved_limits.max_events,
        archived_counts,
    )
    updated = WorkspaceState.from_dict(
        {
            **state.to_dict(),
            "recent_inputs": _trim_recent_inputs(
                state,
                paths.workspace_dir,
                resolved_limits.max_inputs,
                archived_counts,
            ),
            "warnings": _trim_messages(
                state.warnings,
                paths.workspace_dir,
                "warnings",
                resolved_limits.max_warnings,
                archived_counts,
            ),
            "errors": _trim_messages(
                state.errors,
                paths.workspace_dir,
                "errors",
                resolved_limits.max_errors,
                archived_counts,
            ),
            "active_artifacts": _trim_artifacts(
                state,
                paths.workspace_dir,
                resolved_limits.max_active_artifacts,
                archived_counts,
            ),
            "open_tasks": _trim_tasks(
                state,
                paths.workspace_dir,
                resolved_limits.max_done_tasks,
                archived_counts,
            ),
            "context_size": context_size,
        }
    )
    return RetentionResult(state=updated, archived_counts=archived_counts)
