from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from vnalpha.model_routing.config import ModelRoutingConfig
from vnalpha.model_routing.models import ModelProfile, ModelRouteDecision
from vnalpha.model_routing.overrides import ModelRouteOverride
from vnalpha.model_routing.resolver import resolve_model_route


@dataclass(frozen=True, slots=True)
class GatewayRouteRequest:
    stage: str
    task_type: str | None = None
    model_profile: ModelProfile | str | None = None
    route_metadata: Mapping[str, Any] | None = None
    override: ModelRouteOverride | None = None


def resolve_gateway_route(
    config: ModelRoutingConfig,
    request: GatewayRouteRequest,
) -> ModelRouteDecision:
    return resolve_model_route(
        config,
        stage=request.stage,
        task_type=request.task_type,
        model_profile=request.model_profile,
        override=request.override,
        metadata=request.route_metadata,
    )
