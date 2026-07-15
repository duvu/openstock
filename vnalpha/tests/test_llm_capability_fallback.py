from __future__ import annotations

from types import MappingProxyType

import httpx
import pytest

from vnalpha.assistant.errors import (
    LLMNoCompatibleFallbackError,
    LLMResponseError,
)
from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig
from vnalpha.assistant.intent import INTENT_CLASSIFICATION_SCHEMA
from vnalpha.commands.handlers.model import handle_model
from vnalpha.commands.models import CommandStatus, ParsedCommand
from vnalpha.model_routing import (
    ModelCapability,
    ModelProfile,
    ModelRoutingConfig,
    fallback_route_decisions,
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


def test_required_capability_filters_fallbacks_and_keeps_configured_order() -> None:
    config = _routing_config(
        profile_capabilities={
            ModelProfile.SMALL: frozenset(),
            ModelProfile.DEFAULT: frozenset(),
            ModelProfile.REASONING: frozenset({ModelCapability.JSON_SCHEMA}),
            ModelProfile.LONG_CONTEXT: frozenset(),
        }
    )
    primary = resolve_model_route(config, stage="classify")

    fallbacks = fallback_route_decisions(
        config,
        primary,
        required_capability=ModelCapability.JSON_SCHEMA,
    )

    assert [decision.profile for decision in fallbacks] == [ModelProfile.REASONING]
    assert fallbacks[0].capabilities == (ModelCapability.JSON_SCHEMA,)


def test_required_capability_still_skips_duplicate_model_ids() -> None:
    config = _routing_config(
        profile_models={
            ModelProfile.SMALL: "same-model",
            ModelProfile.DEFAULT: "same-model",
            ModelProfile.REASONING: "reasoning-model",
            ModelProfile.LONG_CONTEXT: "long-model",
        },
        profile_capabilities={
            ModelProfile.SMALL: frozenset(),
            ModelProfile.DEFAULT: frozenset({ModelCapability.JSON_SCHEMA}),
            ModelProfile.REASONING: frozenset({ModelCapability.JSON_SCHEMA}),
            ModelProfile.LONG_CONTEXT: frozenset(),
        },
    )
    primary = resolve_model_route(config, stage="classify")

    fallbacks = fallback_route_decisions(
        config,
        primary,
        required_capability="json_schema",
    )

    assert [decision.model_id for decision in fallbacks] == ["reasoning-model"]


def test_strict_schema_uses_first_verified_distinct_fallback(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_LLM_API_KEY", "test-key")
    calls: list[str] = []
    config = _routing_config(
        profile_capabilities={
            ModelProfile.SMALL: frozenset(),
            ModelProfile.DEFAULT: frozenset(),
            ModelProfile.REASONING: frozenset({ModelCapability.JSON_SCHEMA}),
            ModelProfile.LONG_CONTEXT: frozenset(),
        }
    )

    def fake_post(url, *, json, headers, timeout):
        del headers, timeout
        calls.append(json["model"])
        if json["model"] == "primary-model":
            return httpx.Response(
                404,
                request=httpx.Request("POST", url),
                text="model unavailable",
            )
        return _success(url)

    monkeypatch.setattr(httpx, "post", fake_post)
    client = LLMGatewayClient(_gateway_config(), routing_config=config)

    _, usage = client.chat(
        [{"role": "user", "content": "classify"}],
        response_schema=INTENT_CLASSIFICATION_SCHEMA,
        stage="classify",
    )

    assert calls == ["primary-model", "reasoning-model"]
    assert usage["model_route"]["profile"] == "reasoning"
    assert usage["model_route"]["capabilities"] == ["json_schema"]


def test_strict_schema_never_calls_unverified_fallback(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_LLM_API_KEY", "test-key")
    calls: list[str] = []
    config = _routing_config(
        profile_capabilities={profile: frozenset() for profile in ModelProfile}
    )

    def fake_post(url, *, json, headers, timeout):
        del headers, timeout
        calls.append(json["model"])
        return httpx.Response(
            404,
            request=httpx.Request("POST", url),
            text="model unavailable",
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = LLMGatewayClient(_gateway_config(), routing_config=config)

    with pytest.raises(LLMNoCompatibleFallbackError) as captured:
        client.chat(
            [{"role": "user", "content": "classify"}],
            response_schema=INTENT_CLASSIFICATION_SCHEMA,
            stage="classify",
        )

    error = captured.value
    assert calls == ["primary-model"]
    assert error.error_code == "no_compatible_fallback"
    assert error.required_capability == "json_schema"
    assert isinstance(error.primary_error, LLMResponseError)
    assert error.__cause__ is error.primary_error


def test_model_profiles_expose_capabilities_and_strict_fallbacks(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_MODEL_SMALL", "provider/small")
    monkeypatch.setenv("VNALPHA_MODEL_DEFAULT", "provider/default")
    monkeypatch.setenv("VNALPHA_MODEL_REASONING", "provider/reasoning")
    monkeypatch.setenv("VNALPHA_MODEL_LONG_CONTEXT", "provider/long")
    monkeypatch.setenv("VNALPHA_MODEL_CAPABILITIES_DEFAULT", "json_schema")

    result = handle_model(
        ParsedCommand(
            command_name="model",
            raw_text="/model profiles",
            positional=["profiles"],
        )
    )

    assert result.status is CommandStatus.SUCCESS
    content = result.panels[0].content
    assert isinstance(content, dict)
    profiles = {item["profile"]: item for item in content["profiles"]}
    assert profiles["default"]["capabilities"] == ["json_schema"]
    assert profiles["small"]["effective_strict_schema_fallbacks"] == [
        {
            "profile": "default",
            "model_id": "provider/default",
            "capabilities": ["json_schema"],
        }
    ]
