from __future__ import annotations

from dataclasses import dataclass

from vnalpha.model_routing.models import ModelProfile


@dataclass(frozen=True, slots=True)
class ModelRouteOverride:
    session_profile: ModelProfile | None = None
    workspace_profile: ModelProfile | None = None


def resolve_override(override: ModelRouteOverride | None) -> ModelProfile | None:
    if override is None:
        return None
    if override.session_profile is not None:
        return override.session_profile
    return override.workspace_profile
