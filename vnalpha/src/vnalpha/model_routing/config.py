from __future__ import annotations

import os
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from vnalpha.model_routing.models import ModelProfile

DEFAULT_MODEL_ID = "oc-gpt-5.4-mini"


@dataclass(frozen=True, slots=True)
class ModelRoutingConfig:
    default_model_id: str
    profile_models: Mapping[ModelProfile, str]

    @classmethod
    def from_env(cls) -> ModelRoutingConfig:
        default_model_id = os.environ.get("VNALPHA_LLM_MODEL", DEFAULT_MODEL_ID)
        profile_models = {
            ModelProfile.SMALL: os.environ.get(
                "VNALPHA_LLM_MODEL_SMALL", default_model_id
            ),
            ModelProfile.DEFAULT: default_model_id,
            ModelProfile.REASONING: os.environ.get(
                "VNALPHA_LLM_MODEL_REASONING", default_model_id
            ),
            ModelProfile.LONG_CONTEXT: os.environ.get(
                "VNALPHA_LLM_MODEL_LONG_CONTEXT", default_model_id
            ),
        }
        return cls(
            default_model_id=default_model_id,
            profile_models=MappingProxyType(profile_models),
        )

    def model_for(self, profile: ModelProfile) -> str:
        return self.profile_models[profile]
