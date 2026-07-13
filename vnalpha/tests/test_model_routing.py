from __future__ import annotations

import inspect
from types import MappingProxyType

import httpx
import pytest

import vnalpha.model_routing as model_routing
from vnalpha.assistant.gateway import FakeLLMClient, LLMGatewayClient, LLMGatewayConfig
from vnalpha.assistant.intent import IntentClassifier
from vnalpha.commands.handlers.model import handle_model
from vnalpha.commands.models import CommandStatus, ParsedCommand
from vnalpha.model_routing import (
    DEFAULT_OVERRIDE_STORE,
    ModelOverrideStore,
    ModelProfile,
    ModelRouteOverride,
    ModelRoutingConfig,
    fallback_route_decisions,
    profile_for,
    resolve_model_route,
)
from vnalpha.model_routing.observability import (
    emit_route_selected,
    redact_route_metadata,
    route_event,
)


def _config() -> ModelRoutingConfig:
    return ModelRoutingConfig(
        default_model_id="default-model",
        profile_models=MappingProxyType(
            {
                ModelProfile.SMALL: "small-model",
                ModelProfile.DEFAULT: "default-model",
                ModelProfile.REASONING: "reasoning-model",
                ModelProfile.LONG_CONTEXT: "long-model",
            }
        ),
        fallback_profiles=MappingProxyType(
            {
                ModelProfile.SMALL: (ModelProfile.DEFAULT,),
                ModelProfile.DEFAULT: (ModelProfile.SMALL,),
                ModelProfile.REASONING: (
                    ModelProfile.DEFAULT,
                    ModelProfile.SMALL,
                ),
                ModelProfile.LONG_CONTEXT: (
                    ModelProfile.REASONING,
                    ModelProfile.DEFAULT,
                ),
            }
        ),
        explicit_profiles=frozenset({ModelProfile.LONG_CONTEXT}),
    )


def _gateway_config() -> LLMGatewayConfig:
    return LLMGatewayConfig(
        model="default-model",
        endpoint="https://llm.example.test/v1/chat/completions",
        timeout=1,
        max_output_tokens=512,
        max_retries=0,
        store_raw=False,
    )


def test_package_exports_model_routing_boundary() -> None:
    assert model_routing.ModelProfile is ModelProfile
    assert model_routing.resolve_model_route is resolve_model_route
    assert model_routing.DEFAULT_OVERRIDE_STORE is DEFAULT_OVERRIDE_STORE


def test_config_loads_profiles_and_fallbacks(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_MODEL_DEFAULT", "provider/default")
    monkeypatch.setenv("VNALPHA_MODEL_SMALL", "provider/small")
    monkeypatch.setenv("VNALPHA_MODEL_REASONING", "provider/reasoning")
    monkeypatch.setenv("VNALPHA_MODEL_LONG_CONTEXT", "provider/long")
    monkeypatch.setenv("VNALPHA_MODEL_FALLBACK_REASONING", "default,small")

    config = ModelRoutingConfig.from_env()

    assert config.model_for(ModelProfile.SMALL) == "provider/small"
    assert config.model_for(ModelProfile.REASONING) == "provider/reasoning"
    assert config.provider_for(ModelProfile.REASONING) == "provider"
    assert config.fallback_chain(ModelProfile.REASONING) == (
        ModelProfile.DEFAULT,
        ModelProfile.SMALL,
    )
    assert config.is_explicitly_configured(ModelProfile.LONG_CONTEXT)


def test_config_retains_legacy_default_model(monkeypatch) -> None:
    for variable in (
        "VNALPHA_MODEL_DEFAULT",
        "VNALPHA_MODEL_SMALL",
        "VNALPHA_LLM_MODEL_SMALL",
        "VNALPHA_MODEL_REASONING",
        "VNALPHA_LLM_MODEL_REASONING",
        "VNALPHA_MODEL_LONG_CONTEXT",
        "VNALPHA_LLM_MODEL_LONG_CONTEXT",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("VNALPHA_LLM_MODEL", "legacy-model")
    config = ModelRoutingConfig.from_env()
    assert config.model_for(ModelProfile.DEFAULT) == "legacy-model"
    assert config.model_for(ModelProfile.SMALL) == "legacy-model"


def test_config_validation_rejects_missing_profile_model() -> None:
    config = ModelRoutingConfig(
        default_model_id="default",
        profile_models={
            ModelProfile.SMALL: "small",
            ModelProfile.DEFAULT: "default",
            ModelProfile.REASONING: "",
            ModelProfile.LONG_CONTEXT: "long",
        },
    )
    with pytest.raises(ValueError, match="reasoning"):
        config.validate()


def test_policy_routes_stage_task_and_complexity() -> None:
    config = _config()
    assert profile_for(stage="classify", config=config) is ModelProfile.SMALL
    assert (
        profile_for(
            stage="synthesize",
            task_type="deep_symbol_analysis",
            config=config,
        )
        is ModelProfile.REASONING
    )
    assert (
        profile_for(
            stage="synthesize",
            task_type="watchlist_summary",
            metadata={"symbol_count": 5},
            config=config,
        )
        is ModelProfile.DEFAULT
    )
    assert (
        profile_for(
            stage="synthesize",
            task_type="watchlist_summary",
            metadata={"symbol_count": 30},
            config=config,
        )
        is ModelProfile.REASONING
    )
    assert profile_for(stage="compact", config=config) is ModelProfile.LONG_CONTEXT


def test_explicit_profile_wins_over_session_override() -> None:
    decision = resolve_model_route(
        _config(),
        stage="synthesize",
        model_profile=ModelProfile.DEFAULT,
        override=ModelRouteOverride(session_profile=ModelProfile.REASONING),
    )
    assert decision.profile is ModelProfile.DEFAULT
    assert decision.override_source == "per_call"


def test_session_override_wins_over_workspace_override() -> None:
    decision = resolve_model_route(
        _config(),
        stage="classify",
        override=ModelRouteOverride(
            session_profile=ModelProfile.REASONING,
            workspace_profile=ModelProfile.SMALL,
        ),
    )
    assert decision.profile is ModelProfile.REASONING
    assert decision.override_source == "session"


def test_workspace_override_persists_and_reset_clears(tmp_path) -> None:
    store = ModelOverrideStore(workspace_root=tmp_path)
    store.set_override(ModelProfile.SMALL, scope="workspace")

    reloaded = ModelOverrideStore(workspace_root=tmp_path)
    assert reloaded.get_current_override().workspace_profile is ModelProfile.SMALL

    reloaded.clear_override(scope="workspace")
    assert reloaded.get_current_override().workspace_profile is None


def test_fallback_chain_resolves_in_order_and_skips_duplicate_models() -> None:
    decision = resolve_model_route(
        _config(),
        stage="synthesize",
        task_type="deep_symbol_analysis",
    )
    fallbacks = fallback_route_decisions(_config(), decision)
    assert [item.profile for item in fallbacks] == [
        ModelProfile.DEFAULT,
        ModelProfile.SMALL,
    ]

    duplicate_config = ModelRoutingConfig(
        default_model_id="same",
        profile_models=dict.fromkeys(ModelProfile, "same"),
    )
    duplicate_decision = resolve_model_route(duplicate_config, stage="classify")
    assert fallback_route_decisions(duplicate_config, duplicate_decision) == ()


def test_route_event_redacts_raw_prompt_fields() -> None:
    decision = resolve_model_route(_config(), stage="classify")
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


def test_route_selected_emits_audit_event(monkeypatch) -> None:
    captured: list[dict] = []

    def fake_log_audit(event_type, summary, **kwargs):
        captured.append({"event_type": event_type, "summary": summary, **kwargs})

    monkeypatch.setattr("vnalpha.observability.audit.log_audit", fake_log_audit)
    emit_route_selected(resolve_model_route(_config(), stage="classify"))
    assert captured[0]["event_type"] == "MODEL_ROUTE_SELECTED"
    assert captured[0]["extra"]["profile"] == "small"


def test_gateway_sends_selected_model_and_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_LLM_API_KEY", "test-key")
    calls: list[str] = []

    def fake_post(url, *, json, headers, timeout):
        del headers, timeout
        calls.append(json["model"])
        request = httpx.Request("POST", url)
        if json["model"] == "reasoning-model":
            return httpx.Response(404, request=request, text="model unavailable")
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    store = ModelOverrideStore(workspace_root=None)
    client = LLMGatewayClient(
        _gateway_config(), routing_config=_config(), override_store=store
    )
    content, usage = client.chat(
        [{"role": "user", "content": "analyze"}],
        stage="synthesize",
        task_type="deep_symbol_analysis",
    )

    assert content == "ok"
    assert calls == ["reasoning-model", "default-model"]
    assert usage["model_route"]["profile"] == "default"
    assert client.last_route_decision is not None
    assert client.last_route_decision.profile is ModelProfile.DEFAULT


def test_classifier_retries_invalid_small_json_with_default_profile() -> None:
    client = FakeLLMClient(
        responses=[
            ("not-json", {}),
            (
                '{"intent":"scan_candidates","confidence":0.9,"entities":{},'
                '"needs_clarification":false,"clarification_question":null,'
                '"safety_flags":[]}',
                {},
            ),
        ]
    )
    result = IntentClassifier(client).classify("show candidates")
    assert result.intent == "scan_candidates"
    assert client.call_metadata[0]["task_type"] == "intent_classification"
    assert client.call_metadata[0]["model_profile"] is None
    assert client.call_metadata[1]["model_profile"] == "default"


def test_model_commands_set_status_and_reset(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    DEFAULT_OVERRIDE_STORE.clear_override(scope="all")

    use_result = handle_model(
        ParsedCommand(
            command_name="model",
            raw_text="/model use small --scope session",
            positional=["use", "small"],
            options={"scope": "session"},
        )
    )
    assert use_result.status is CommandStatus.SUCCESS
    assert "small" in (use_result.summary or "")

    status_result = handle_model(
        ParsedCommand(
            command_name="model",
            raw_text="/model status",
            positional=["status"],
        )
    )
    assert isinstance(status_result.panels[0].content, dict)
    assert status_result.panels[0].content["active_override"] == "small"

    reset_result = handle_model(
        ParsedCommand(
            command_name="model",
            raw_text="/model reset",
            positional=["reset"],
        )
    )
    assert reset_result.status is CommandStatus.SUCCESS
    assert DEFAULT_OVERRIDE_STORE.get_current_override().session_profile is None


def test_session_overrides_are_isolated_and_cleanup_by_session() -> None:
    store = ModelOverrideStore()

    store.set_override("small", scope="session", session_id="session-a")
    store.set_override("reasoning", scope="session", session_id="session-b")

    assert (
        store.get_current_override(session_id="session-a").session_profile
        is ModelProfile.SMALL
    )
    assert (
        store.get_current_override(session_id="session-b").session_profile
        is ModelProfile.REASONING
    )

    client = LLMGatewayClient(
        LLMGatewayConfig(
            model="default-model",
            endpoint="https://example.invalid",
            timeout=1,
            max_output_tokens=1,
            max_retries=0,
            store_raw=False,
        ),
        routing_config=_config(),
        override_store=store,
    )
    session_b_route = client.resolve_route(
        stage="classify", route_metadata={"session_id": "session-b"}
    )
    assert session_b_route.profile is ModelProfile.REASONING

    store.clear_override(scope="session", session_id="session-a")

    assert store.get_current_override(session_id="session-a").session_profile is None
    assert (
        store.get_current_override(session_id="session-b").session_profile
        is ModelProfile.REASONING
    )


def test_gateway_routing_parameters_are_keyword_only() -> None:
    signature = inspect.signature(LLMGatewayClient.chat)
    for name in ("task_type", "model_profile", "route_metadata"):
        parameter = signature.parameters[name]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is None


def test_chat_controller_close_clears_session_override() -> None:
    from vnalpha.chat.controller import ChatController

    DEFAULT_OVERRIDE_STORE.clear_override(scope="all")
    try:
        DEFAULT_OVERRIDE_STORE.set_override(
            "small", scope="session", session_id="chat-session"
        )
        controller = ChatController(
            on_message=lambda _style, _text: None,
            chat_session_id="chat-session",
        )

        controller.close()

        assert (
            DEFAULT_OVERRIDE_STORE.get_current_override(
                session_id="chat-session"
            ).session_profile
            is None
        )
    finally:
        DEFAULT_OVERRIDE_STORE.clear_override(scope="all")


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
