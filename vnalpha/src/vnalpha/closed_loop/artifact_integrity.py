from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from vnalpha.closed_loop.errors import ClosedLoopBoundaryError, ClosedLoopNotFoundError
from vnalpha.closed_loop.models import JsonObject
from vnalpha.closed_loop.paths import ensure_tree_confined, validate_identifier
from vnalpha.closed_loop.store import ClosedLoopStore


def resolve_artifact_root(root: Path, artifact_id: str) -> Path | None:
    try:
        artifact_id = validate_identifier(artifact_id, "artifact_id")
    except (ClosedLoopBoundaryError, ClosedLoopNotFoundError):
        return None
    candidates = (
        root / "research" / artifact_id,
        root / "artifacts" / artifact_id,
    )
    for candidate in candidates:
        try:
            confined = ensure_tree_confined(root, candidate, "artifact root")
        except ClosedLoopBoundaryError:
            continue
        if confined.is_dir():
            return confined
    runs_root = root / "runs"
    try:
        ensure_tree_confined(root, runs_root, "runs root")
    except ClosedLoopBoundaryError:
        return None
    if runs_root.exists():
        for run_dir in runs_root.iterdir():
            try:
                candidate = ensure_tree_confined(
                    root, run_dir / "research" / artifact_id, "artifact root"
                )
            except ClosedLoopBoundaryError:
                continue
            if candidate.is_dir():
                return candidate
    return None


def resolve_requested_root(
    store: ClosedLoopStore, artifact_id: str, artifact_root: Path | None
) -> Path | None:
    try:
        if artifact_root is not None:
            return store.scoped_directory(artifact_root, "artifact root")
        return resolve_artifact_root(store.root, artifact_id)
    except (ClosedLoopBoundaryError, ClosedLoopNotFoundError):
        return None


def artifact_digest(root: Path) -> str:
    confined = ensure_tree_confined(root, root, "artifact root")
    digest = sha256()
    excluded = {"promotion.json", "validation-report.json"}
    files = sorted(
        path for path in confined.rglob("*") if path.is_file() or path.is_symlink()
    )
    for path in files:
        safe_path = ensure_tree_confined(confined, path, "artifact file")
        if path.name in excluded:
            continue
        digest.update(path.relative_to(confined).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(safe_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def read_json(path: Path | None) -> JsonObject:
    text = read_text(path)
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
