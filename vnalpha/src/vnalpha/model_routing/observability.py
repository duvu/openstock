from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, TypedDict

from vnalpha.model_routing.models import ModelRouteDecision


class RouteMetadata(TypedDict, total=False):
    request_id: str
    session_id: str
    workspace_id: str
    surface: str


@dataclass(frozen=True, slots=True)
class ModelRouteEvent:
    profile: str
    model_id: str
    stage: str
    task_type: str | None
    route_reason: str
    metadata: Mapping[str, str]


def redact_route_metadata(metadata: Mapping[str, str]) -> RouteMetadata:
    redacted: RouteMetadata = {}
    for key in ("request_id", "session_id", "workspace_id", "surface"):
        value = metadata.get(key)
        if value is not None:
            redacted[key] = value
    return redacted


def route_event(
    decision: ModelRouteDecision,
    metadata: RouteMetadata | None = None,
) -> ModelRouteEvent:
    return ModelRouteEvent(
        profile=decision.profile.value,
        model_id=decision.model_id,
        stage=decision.stage,
        task_type=decision.task_type,
        route_reason=decision.route_reason,
        metadata=MappingProxyType(dict(metadata or {})),
    )
