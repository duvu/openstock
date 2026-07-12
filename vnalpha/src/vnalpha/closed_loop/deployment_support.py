from __future__ import annotations

import json
from pathlib import Path

from vnalpha.closed_loop.errors import (
    ClosedLoopBoundaryError,
    ClosedLoopNotFoundError,
    ClosedLoopPersistenceError,
)
from vnalpha.closed_loop.models import (
    DeploymentState,
    PromotableArtifactType,
    PromotionVerification,
)
from vnalpha.closed_loop.paths import validate_identifier
from vnalpha.closed_loop.policy import parse_artifact_type, prohibited_behaviors
from vnalpha.closed_loop.store import ClosedLoopStore


def safe_identifier(value: str, field: str) -> str:
    return validate_identifier(value, field)


def manifest_type(root: Path | None) -> PromotableArtifactType | None:
    if root is None:
        return None
    path = root / "manifest.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(
        payload.get("artifact_type"), str
    ):
        return None
    try:
        return parse_artifact_type(payload["artifact_type"])
    except ValueError:
        return None


def candidate_is_safe(root: Path, candidate: str) -> bool:
    try:
        code = (root / "generated_code.py").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return not prohibited_behaviors(f"{candidate}\n{code}")


def verified_artifact_root(
    store: ClosedLoopStore, verification: PromotionVerification
) -> Path | None:
    if verification.artifact_root is None:
        return None
    try:
        return store.scoped_directory(Path(verification.artifact_root), "artifact root")
    except (ClosedLoopBoundaryError, ClosedLoopNotFoundError):
        return None


def write_promotion_marker(
    store: ClosedLoopStore, state: DeploymentState, status: str, reason: str
) -> None:
    if state.artifact_root is None:
        return
    root = store.scoped_directory(Path(state.artifact_root), "artifact root")
    path = store.scoped_path(root / "promotion.json", "promotion marker")
    payload = {
        "artifact_id": state.candidate,
        "deployment_id": state.deployment_id,
        "status": status,
        "updated_at": state.updated_at,
        "reason": reason,
    }
    try:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        raise ClosedLoopPersistenceError(f"could not write {path}") from exc
