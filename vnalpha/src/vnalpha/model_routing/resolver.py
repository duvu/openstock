from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from vnalpha.model_routing.config import ModelRoutingConfig
from vnalpha.model_routing.models import ModelProfile, ModelRouteDecision
from vnalpha.model_routing.overrides import (
    ModelRouteOverride,
    resolve_override_with_source,
)
from vnalpha.model_routing.policy import profile_for


def resolve_model_route(
    config: ModelRoutingConfig,
    *,
    stage: str,
    task_type: str | None = None,
    model_profile: ModelProfile | str | None = None,
    override: ModelRouteOverride | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ModelRouteDecision:
    if model_profile is not None:
        profile = ModelProfile.parse(model_profile)
        return decision_for_profile(
            config,
            profile=profile,
            stage=stage,
            task_type=task_type,
            route_reason="explicit_profile",
            override_source="per_call",
        )

    override_profile, override_source = resolve_override_with_source(override)
    if override_profile is not None:
        return decision_for_profile(
            config,
            profile=override_profile,
            stage=stage,
            task_type=task_type,
            route_reason="override_profile",
            override_source=override_source,
        )

    profile = profile_for(
        stage=stage,
        task_type=task_type,
        metadata=metadata,
        config=config,
    )
    normalized_stage = stage.strip().lower().replace("-", "_")
    route_reason = (
        "stage_task_policy"
        if normalized_stage
        in {"classify", "plan", "synthesize", "compact", "title", "diagnose"}
        or task_type
        else "default_profile"
    )
    return decision_for_profile(
        config,
        profile=profile,
        stage=stage,
        task_type=task_type,
        route_reason=route_reason,
        override_source=None,
    )


def decision_for_profile(
    config: ModelRoutingConfig,
    *,
    profile: ModelProfile,
    stage: str,
    task_type: str | None,
    route_reason: str,
    override_source: str | None = None,
    fallback_chain: tuple[ModelProfile, ...] | None = None,
) -> ModelRouteDecision:
    return ModelRouteDecision(
        profile=profile,
        model_id=config.model_for(profile),
        stage=stage,
        task_type=task_type,
        route_reason=route_reason,
        provider=config.provider_for(profile),
        override_source=override_source,
        fallback_chain=(
            config.fallback_chain(profile)
            if fallback_chain is None
            else fallback_chain
        ),
    )


def fallback_route_decisions(
    config: ModelRoutingConfig, decision: ModelRouteDecision
) -> tuple[ModelRouteDecision, ...]:
    decisions: list[ModelRouteDecision] = []
    seen_profiles: set[ModelProfile] = {decision.profile}
    seen_model_ids: set[str] = {decision.model_id}
    for profile in decision.fallback_chain:
        model_id = config.model_for(profile)
        if profile in seen_profiles or model_id in seen_model_ids:
            continue
        seen_profiles.add(profile)
        seen_model_ids.add(model_id)
        decisions.append(
            decision_for_profile(
                config,
                profile=profile,
                stage=decision.stage,
                task_type=decision.task_type,
                route_reason="fallback_profile",
                override_source=decision.override_source,
                fallback_chain=(),
            )
        )
    return tuple(decisions)
