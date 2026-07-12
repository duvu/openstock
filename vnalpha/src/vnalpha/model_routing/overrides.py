from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from vnalpha.model_routing.models import ModelProfile

_OVERRIDE_FILE = "model-routing.json"


@dataclass(frozen=True, slots=True)
class ModelRouteOverride:
    session_profile: ModelProfile | None = None
    workspace_profile: ModelProfile | None = None


class ModelOverrideStore:
    """Bounded profile override store with optional workspace persistence."""

    def __init__(self, *, workspace_root: Path | None = None) -> None:
        self._session_profiles: dict[str | None, ModelProfile] = {}
        self._workspace_root = workspace_root
        self._lock = RLock()

    def get_current_override(
        self,
        workspace_id: str | None = None,
        *,
        session_id: str | None = None,
    ) -> ModelRouteOverride:
        with self._lock:
            return ModelRouteOverride(
                session_profile=self._session_profiles.get(session_id),
                workspace_profile=self._load_workspace_profile(workspace_id),
            )

    def set_override(
        self,
        profile: ModelProfile | str,
        *,
        scope: str = "workspace",
        workspace_id: str | None = None,
        session_id: str | None = None,
    ) -> ModelRouteOverride:
        parsed = ModelProfile.parse(profile)
        normalized_scope = scope.strip().lower()
        with self._lock:
            if normalized_scope == "session":
                self._session_profiles[session_id] = parsed
            elif normalized_scope == "workspace":
                self._write_workspace_profile(parsed, workspace_id)
            else:
                raise ValueError(
                    "Model override scope must be 'session' or 'workspace'."
                )
        self._emit_override_event("MODEL_OVERRIDE_SET", parsed, normalized_scope)
        return self.get_current_override(workspace_id, session_id=session_id)

    def clear_override(
        self,
        *,
        scope: str = "all",
        workspace_id: str | None = None,
        session_id: str | None = None,
    ) -> ModelRouteOverride:
        normalized_scope = scope.strip().lower()
        with self._lock:
            if normalized_scope in {"all", "session"}:
                if normalized_scope == "all":
                    self._session_profiles.clear()
                else:
                    self._session_profiles.pop(session_id, None)
            if normalized_scope in {"all", "workspace"}:
                path = self._workspace_override_path(workspace_id, create=False)
                if path is not None:
                    from vnalpha.workspace_context.locking import workspace_transaction

                    with workspace_transaction(
                        path.parent.name,
                        root=path.parent.parent,
                    ):
                        path.unlink(missing_ok=True)
            if normalized_scope not in {"all", "session", "workspace"}:
                raise ValueError(
                    "Model override reset scope must be 'all', 'session', or 'workspace'."
                )
        self._emit_override_event("MODEL_OVERRIDE_CLEARED", None, normalized_scope)
        return self.get_current_override(workspace_id, session_id=session_id)

    def _load_workspace_profile(self, workspace_id: str | None) -> ModelProfile | None:
        path = self._workspace_override_path(workspace_id, create=False)
        if path is None or not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            value = payload.get("profile")
            return ModelProfile.parse(value) if value else None
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def _write_workspace_profile(
        self, profile: ModelProfile, workspace_id: str | None
    ) -> None:
        path = self._workspace_override_path(workspace_id, create=True)
        if path is None:
            raise RuntimeError("No active workspace is available for model override.")
        payload = json.dumps(
            {"profile": profile.value, "scope": "workspace"},
            indent=2,
            sort_keys=True,
        )
        try:
            from vnalpha.workspace_context.locking import workspace_transaction
            from vnalpha.workspace_context.storage import _atomic_write_text

            with workspace_transaction(path.parent.name, root=path.parent.parent):
                _atomic_write_text(path, payload)
        except ImportError:
            path.write_text(payload, encoding="utf-8")

    def _workspace_override_path(
        self, workspace_id: str | None, *, create: bool
    ) -> Path | None:
        try:
            from vnalpha.workspace_context.storage import (
                load_latest_workspace_id,
                resolve_workspace_root,
            )

            root = resolve_workspace_root(self._workspace_root)
            resolved_id = workspace_id or load_latest_workspace_id(root=root)
            if resolved_id is None:
                if not create:
                    return None
                from vnalpha.workspace_context.lifecycle import create_workspace

                resolved_id = create_workspace(root=root).workspace_id
            workspace_dir = root / resolved_id
            if create:
                workspace_dir.mkdir(parents=True, exist_ok=True)
            return workspace_dir / _OVERRIDE_FILE
        except (ImportError, OSError, ValueError):
            return None

    @staticmethod
    def _emit_override_event(
        event_type: str, profile: ModelProfile | None, scope: str
    ) -> None:
        try:
            from vnalpha.model_routing.observability import emit_override_event

            emit_override_event(event_type, profile=profile, scope=scope)
        except Exception:
            pass


def resolve_override(override: ModelRouteOverride | None) -> ModelProfile | None:
    profile, _source = resolve_override_with_source(override)
    return profile


def resolve_override_with_source(
    override: ModelRouteOverride | None,
) -> tuple[ModelProfile | None, str | None]:
    if override is None:
        return None, None
    if override.session_profile is not None:
        return override.session_profile, "session"
    if override.workspace_profile is not None:
        return override.workspace_profile, "workspace"
    return None, None


DEFAULT_OVERRIDE_STORE = ModelOverrideStore()
