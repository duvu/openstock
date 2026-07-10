from __future__ import annotations

import inspect

import vnalpha.model_routing as model_routing
from vnalpha.assistant.gateway import FakeLLMClient, LLMGatewayClient, LLMGatewayConfig
from vnalpha.model_routing import (
    ModelProfile,
    ModelRoutingConfig,
    profile_for,
    resolve_model_route,
)
from vnalpha.model_routing.observability import redact_route_metadata, route_event


def test_package_exports_model_routing_boundary() -> None:
    assert model_routing.ModelProfile is ModelProfile
    assert model_routing.resolve_model_route is resolve_model_route


def test_default_route_uses_existing_configured_model(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_LLM_MODEL", "legacy-model")

    decision = resolve_model_route(
        ModelRoutingConfig.from_env(),
        stage="unknown",
    )

    assert decision.profile is ModelProfile.DEFAULT
    assert decision.model_id == "legacy-model"
    assert decision.route_reason == "default_profile"


def test_explicit_profile_resolves_deterministically(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_LLM_MODEL", "legacy-model")
    monkeypatch.setenv("VNALPHA_LLM_MODEL_REASONING", "reasoning-model")

    decision = resolve_model_route(
        ModelRoutingConfig.from_env(),
        stage="plan",
        model_profile=ModelProfile.REASONING,
    )

    assert decision.profile is ModelProfile.REASONING
    assert decision.model_id == "reasoning-model"
    assert decision.route_reason == "explicit_profile"


def test_stage_policy_is_deterministic() -> None:
    assert profile_for(stage="classify") is ModelProfile.SMALL


def test_route_event_redacts_raw_prompt_fields(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_LLM_MODEL", "legacy-model")
    decision = resolve_model_route(ModelRoutingConfig.from_env(), stage="classify")

    metadata = redact_route_metadata(
        {
            "request_id": "request-1",
            "prompt": "raw confidential prompt",
            "content": "raw message content",
        }
    )
    event = route_event(decision, metadata)

    assert event.metadata == {"request_id": "request-1"}
    assert "raw confidential prompt" not in str(event)
    assert "raw message content" not in str(event)


def test_gateway_config_retains_vnalpha_llm_model(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_LLM_MODEL", "legacy-model")

    assert LLMGatewayConfig.from_env().model == "legacy-model"


def test_gateway_routing_metadata_parameters_are_keyword_only() -> None:
    signature = inspect.signature(LLMGatewayClient.chat)

    for name in ("task_type", "model_profile", "route_metadata"):
        parameter = signature.parameters[name]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is None


def test_fake_gateway_accepts_metadata_without_changing_legacy_calls() -> None:
    client = FakeLLMClient(responses=[("first", {}), ("second", {})])
    legacy_messages = [{"role": "user", "content": "legacy"}]
    routed_messages = [{"role": "user", "content": "routed"}]

    assert client.chat(legacy_messages) == ("first", {})
    assert client.chat(
        routed_messages,
        stage="classify",
        task_type="intent_classification",
        model_profile="small",
        route_metadata={"request_id": "request-1"},
    ) == ("second", {})

    assert client.calls == [legacy_messages, routed_messages]
