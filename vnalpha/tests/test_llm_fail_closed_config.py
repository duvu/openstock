from __future__ import annotations

import httpx
import pytest

from vnalpha.assistant.errors import LLMConfigError
from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig
from vnalpha.commands.handlers.model import handle_model
from vnalpha.commands.models import CommandStatus, ParsedCommand
from vnalpha.model_routing.config import ModelRoutingConfig

_LLM_ENV = (
    "VNALPHA_LLM_ENDPOINT",
    "VNALPHA_LLM_MODEL",
    "VNALPHA_MODEL_DEFAULT",
    "VNALPHA_MODEL_SMALL",
    "VNALPHA_MODEL_REASONING",
    "VNALPHA_MODEL_LONG_CONTEXT",
    "VNALPHA_LLM_API_KEY",
    "OPENAI_API_KEY",
)


def _clear_llm_env(monkeypatch) -> None:
    for name in _LLM_ENV:
        monkeypatch.delenv(name, raising=False)


def _fail_if_called(*_args, **_kwargs):
    raise AssertionError("network must not be called for invalid LLM configuration")


def test_unconfigured_gateway_fails_before_route_or_network(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setattr(httpx, "post", _fail_if_called)

    with pytest.raises(LLMConfigError, match="VNALPHA_LLM_ENDPOINT"):
        LLMGatewayClient(LLMGatewayConfig.from_env())


def test_global_openai_key_does_not_enable_assistant(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv(
        "VNALPHA_LLM_ENDPOINT", "https://gateway.example.test/v1/chat/completions"
    )
    monkeypatch.setenv("VNALPHA_LLM_MODEL", "verified-model")
    monkeypatch.setenv("OPENAI_API_KEY", "global-key-must-not-be-used")
    monkeypatch.setattr(httpx, "post", _fail_if_called)

    client = LLMGatewayClient(LLMGatewayConfig.from_env())
    with pytest.raises(LLMConfigError, match="VNALPHA_LLM_API_KEY"):
        client.chat([{"role": "user", "content": "classify"}], stage="classify")


@pytest.mark.parametrize(
    ("endpoint", "model", "pattern"),
    [
        ("", "verified-model", "VNALPHA_LLM_ENDPOINT"),
        (
            "https://gateway.example.test/v1/chat/completions",
            "",
            "VNALPHA_MODEL_DEFAULT",
        ),
        ("ftp://gateway.example.test/chat", "verified-model", "http:// or https://"),
    ],
)
def test_missing_or_invalid_gateway_fields_fail_before_network(
    monkeypatch, endpoint, model, pattern
) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("VNALPHA_LLM_ENDPOINT", endpoint)
    monkeypatch.setenv("VNALPHA_LLM_MODEL", model)
    monkeypatch.setattr(httpx, "post", _fail_if_called)

    with pytest.raises(LLMConfigError, match=pattern):
        LLMGatewayClient(LLMGatewayConfig.from_env())


def test_explicit_dedicated_configuration_keeps_bounded_call_path(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    endpoint = "https://gateway.example.test/v1/chat/completions"
    monkeypatch.setenv("VNALPHA_LLM_ENDPOINT", endpoint)
    monkeypatch.setenv("VNALPHA_MODEL_DEFAULT", "verified-model")
    monkeypatch.setenv("VNALPHA_LLM_API_KEY", "dedicated-test-key")
    captured: dict = {}

    def fake_post(url, *, json, headers, timeout):
        captured.update(
            {
                "url": url,
                "model": json["model"],
                "authorization": headers["Authorization"],
                "timeout": timeout,
            }
        )
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {},
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    content, _usage = LLMGatewayClient(LLMGatewayConfig.from_env()).chat(
        [{"role": "user", "content": "hello"}], stage="generic"
    )

    assert content == "ok"
    assert captured == {
        "url": endpoint,
        "model": "verified-model",
        "authorization": "Bearer dedicated-test-key",
        "timeout": 30,
    }


def test_model_routing_has_no_built_in_model(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)

    with pytest.raises(ValueError, match="Missing configured model id"):
        ModelRoutingConfig.from_env()


def test_model_status_reports_disabled_without_configuration(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)

    result = handle_model(
        ParsedCommand(
            command_name="model", raw_text="/model status", positional=["status"]
        )
    )

    assert result.status is CommandStatus.PARTIAL
    assert result.panels[0].content["routing_mode"] == "disabled"
    assert result.panels[0].content["configured"] is False
    assert result.panels[0].content["resolved_models"] == {}
