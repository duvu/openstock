from __future__ import annotations

import os
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from vnalpha.model_routing.models import ModelProfile

DEFAULT_MODEL_ID = ""

_DEFAULT_FALLBACKS: Mapping[ModelProfile, tuple[ModelProfile, ...]] = MappingProxyType(
    {
        ModelProfile.SMALL: (ModelProfile.DEFAULT,),
        ModelProfile.DEFAULT: (ModelProfile.SMALL,),
        ModelProfile.REASONING: (ModelProfile.DEFAULT, ModelProfile.SMALL),
        ModelProfile.LONG_CONTEXT: (
            ModelProfile.REASONING,
            ModelProfile.DEFAULT,
        ),
    }
)


def _first_env(*names: str, default: str = "") -> tuple[str, bool]:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value, True
    return default, False


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_fallbacks(profile: ModelProfile) -> tuple[ModelProfile, ...]:
    key = profile.value.upper()
    raw, configured = _first_env(
        f"VNALPHA_MODEL_FALLBACK_{key}",
        f"VNALPHA_MODEL_FALLBACKS_{key}",
    )
    if not configured:
        return _DEFAULT_FALLBACKS[profile]
    parsed: list[ModelProfile] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        candidate = ModelProfile.parse(item)
        if candidate is profile or candidate in parsed:
            continue
        parsed.append(candidate)
    return tuple(parsed)


def _provider_from_model_id(model_id: str) -> str | None:
    if "/" not in model_id:
        return None
    provider, _separator, _name = model_id.partition("/")
    return provider or None


@dataclass(frozen=True, slots=True)
class ModelRoutingConfig:
    default_model_id: str
    profile_models: Mapping[ModelProfile, str]
    fallback_profiles: Mapping[ModelProfile, tuple[ModelProfile, ...]] = field(
        default_factory=lambda: _DEFAULT_FALLBACKS
    )
    explicit_profiles: frozenset[ModelProfile] = frozenset()
    allow_raw_override: bool = False

    @classmethod
    def from_env(cls, *, default_model_id: str | None = None) -> ModelRoutingConfig:
        legacy_default = default_model_id or DEFAULT_MODEL_ID
        default_id, default_explicit = _first_env(
            "VNALPHA_MODEL_DEFAULT",
            "VNALPHA_LLM_MODEL",
            default=legacy_default,
        )
        small_id, small_explicit = _first_env(
            "VNALPHA_MODEL_SMALL",
            "VNALPHA_LLM_MODEL_SMALL",
            default=default_id,
        )
        reasoning_id, reasoning_explicit = _first_env(
            "VNALPHA_MODEL_REASONING",
            "VNALPHA_LLM_MODEL_REASONING",
            default=default_id,
        )
        long_context_id, long_context_explicit = _first_env(
            "VNALPHA_MODEL_LONG_CONTEXT",
            "VNALPHA_LLM_MODEL_LONG_CONTEXT",
            default=reasoning_id,
        )
        profile_models = MappingProxyType(
            {
                ModelProfile.SMALL: small_id,
                ModelProfile.DEFAULT: default_id,
                ModelProfile.REASONING: reasoning_id,
                ModelProfile.LONG_CONTEXT: long_context_id,
            }
        )
        explicit_profiles = frozenset(
            profile
            for profile, configured in (
                (ModelProfile.SMALL, small_explicit),
                (ModelProfile.DEFAULT, default_explicit),
                (ModelProfile.REASONING, reasoning_explicit),
                (ModelProfile.LONG_CONTEXT, long_context_explicit),
            )
            if configured
        )
        config = cls(
            default_model_id=default_id,
            profile_models=profile_models,
            fallback_profiles=MappingProxyType(
                {profile: _parse_fallbacks(profile) for profile in ModelProfile}
            ),
            explicit_profiles=explicit_profiles,
            allow_raw_override=_parse_bool(
                os.environ.get("VNALPHA_MODEL_ALLOW_RAW_OVERRIDE"), default=False
            ),
        )
        config.validate()
        return config

    def validate(self) -> None:
        missing = [
            profile.value
            for profile in ModelProfile
            if not self.profile_models.get(profile, "").strip()
        ]
        if missing:
            raise ValueError(
                "Missing configured model id for profile(s): " + ", ".join(missing)
            )
        for profile, fallbacks in self.fallback_profiles.items():
            if not isinstance(profile, ModelProfile):
                raise ValueError(f"Invalid fallback source profile: {profile!r}")
            for fallback in fallbacks:
                if fallback not in self.profile_models:
                    raise ValueError(
                        f"Fallback profile '{fallback.value}' is not configured."
                    )

    def model_for(self, profile: ModelProfile) -> str:
        return self.profile_models[profile]

    def provider_for(self, profile: ModelProfile) -> str | None:
        return _provider_from_model_id(self.model_for(profile))

    def fallback_chain(self, profile: ModelProfile) -> tuple[ModelProfile, ...]:
        return self.fallback_profiles.get(profile, ())

    def is_explicitly_configured(self, profile: ModelProfile) -> bool:
        return profile in self.explicit_profiles
