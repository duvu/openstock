from __future__ import annotations

from types import MappingProxyType

import httpx

from vnalpha.assistant.gateway import LLMGatewayConfig
from vnalpha.model_routing import (
    ModelCapability,
    ModelProfile,
    ModelRoutingConfig,
    resolve_model_route,
)


def _gateway_config() -> LLMGatewayConfig:
    return LLMGatewayConfig(
        model="primary-model",
        endpoint="https://llm.example.test/v1/chat/completions",
        timeout=1,
        max_output_tokens=256,
        max_retries=0,
        store_raw=False,
    )


def _routing_config(
    *,
    profile_capabilities: dict[ModelProfile, frozenset[ModelCapability]] | None = None,
    profile_models: dict[ModelProfile, str] | None = None,
    fallback_profiles: dict[ModelProfile, tuple[ModelProfile, ...]] | None = None,
) -> ModelRoutingConfig:
    return ModelRoutingConfig(
        default_model_id="default-model",
        profile_models=MappingProxyType(
            profile_models
            or {
                ModelProfile.SMALL: "primary-model",
                ModelProfile.DEFAULT: "default-model",
                ModelProfile.REASONING: "reasoning-model",
                ModelProfile.LONG_CONTEXT: "long-model",
            }
        ),
        fallback_profiles=MappingProxyType(
            fallback_profiles
            or {
                ModelProfile.SMALL: (
                    ModelProfile.DEFAULT,
                    ModelProfile.REASONING,
                ),
                ModelProfile.DEFAULT: (ModelProfile.SMALL,),
                ModelProfile.REASONING: (ModelProfile.DEFAULT,),
                ModelProfile.LONG_CONTEXT: (ModelProfile.REASONING,),
            }
        ),
        profile_capabilities=MappingProxyType(
            profile_capabilities or {profile: frozenset() for profile in ModelProfile}
        ),
    )


def _success(url: str, content: str = '{"ok": true}') -> httpx.Response:
    return httpx.Response(
        200,
        request=httpx.Request("POST", url),
        json={
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )


def test_route_decision_carries_configured_capabilities() -> None:
    config = _routing_config(
        profile_capabilities={
            ModelProfile.SMALL: frozenset(),
            ModelProfile.DEFAULT: frozenset({ModelCapability.JSON_SCHEMA}),
            ModelProfile.REASONING: frozenset(),
            ModelProfile.LONG_CONTEXT: frozenset(),
        }
    )

    decision = resolve_model_route(
        config,
        stage="synthesize",
        model_profile=ModelProfile.DEFAULT,
    )

    assert decision.capabilities == (ModelCapability.JSON_SCHEMA,)
    assert decision.supports(ModelCapability.JSON_SCHEMA)
    assert decision.to_dict()["capabilities"] == ["json_schema"]
