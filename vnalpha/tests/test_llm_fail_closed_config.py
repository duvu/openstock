from __future__ import annotations

import httpx
import pytest

from vnalpha.assistant.errors import LLMConfigError
from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig

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
