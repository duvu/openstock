from __future__ import annotations

from vnalpha.model_routing.models import ModelProfile


def profile_for(
    *,
    stage: str,
    explicit_profile: ModelProfile | None = None,
) -> ModelProfile:
    if explicit_profile is not None:
        return explicit_profile
    return default_profile_for_stage(stage)


def default_profile_for_stage(stage: str) -> ModelProfile:
    match stage:
        case "classify":
            return ModelProfile.SMALL
        case "plan":
            return ModelProfile.REASONING
        case "synthesize":
            return ModelProfile.DEFAULT
        case _:
            return ModelProfile.DEFAULT
