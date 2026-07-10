from __future__ import annotations

from vnalpha.model_routing.config import ModelRoutingConfig
from vnalpha.model_routing.models import ModelProfile, ModelRouteDecision
from vnalpha.model_routing.overrides import ModelRouteOverride, resolve_override
from vnalpha.model_routing.policy import profile_for


def resolve_model_route(
    config: ModelRoutingConfig,
    *,
    stage: str,
    task_type: str | None = None,
    model_profile: ModelProfile | None = None,
    override: ModelRouteOverride | None = None,
) -> ModelRouteDecision:
    override_profile = resolve_override(override)
    if override_profile is not None:
        return _decision(
            config,
            override_profile,
            stage,
            task_type,
            "override_profile",
        )
    if model_profile is not None:
        return _decision(
            config,
            model_profile,
            stage,
            task_type,
            "explicit_profile",
        )
    profile = profile_for(stage=stage)
    route_reason = (
        "stage_policy"
        if stage in {"classify", "plan", "synthesize"}
        else "default_profile"
    )
    return _decision(config, profile, stage, task_type, route_reason)


def _decision(
    config: ModelRoutingConfig,
    profile: ModelProfile,
    stage: str,
    task_type: str | None,
    route_reason: str,
) -> ModelRouteDecision:
    return ModelRouteDecision(
        profile=profile,
        model_id=config.model_for(profile),
        stage=stage,
        task_type=task_type,
        route_reason=route_reason,
    )
