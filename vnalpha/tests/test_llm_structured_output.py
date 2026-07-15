from __future__ import annotations

import copy
import json

import httpx
import pytest

from vnalpha.assistant.errors import LLMResponseError, LLMTimeoutError
from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig
from vnalpha.assistant.intent import INTENT_CLASSIFICATION_SCHEMA
from vnalpha.assistant.synthesizer import SYNTHESIS_RESPONSE_SCHEMA


def _client() -> LLMGatewayClient:
    return LLMGatewayClient(
        LLMGatewayConfig(
            model="test-model",
            endpoint="https://llm.example.test/v1/chat/completions",
            timeout=1,
            max_output_tokens=256,
            max_retries=0,
            store_raw=False,
        )
    )


def _success(url: str, content: str) -> httpx.Response:
    return httpx.Response(
        200,
        request=httpx.Request("POST", url),
        json={
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )


def test_gateway_sends_strict_json_schema(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_LLM_API_KEY", "test")
    payloads: list[dict] = []

    def fake_post(url, *, json, headers, timeout):
        del headers, timeout
        payloads.append(copy.deepcopy(json))
        return _success(
            url,
            '{"intent":"scan_candidates","confidence":1,"entities":{},'
            '"needs_clarification":false,"clarification_question":null,'
            '"safety_flags":[]}',
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    _, usage = _client().chat(
        [{"role": "user", "content": "classify"}],
        response_schema=INTENT_CLASSIFICATION_SCHEMA,
        stage="classify",
    )

    response_format = payloads[0]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"] == INTENT_CLASSIFICATION_SCHEMA
    assert usage["structured_output_mode"] == "json_schema"
    assert usage["structured_output_downgraded"] is False


def test_gateway_downgrades_once_when_endpoint_rejects_json_schema(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_LLM_API_KEY", "test")
    payloads: list[dict] = []

    def fake_post(url, *, json, headers, timeout):
        del headers, timeout
        payloads.append(copy.deepcopy(json))
        if len(payloads) == 1:
            return httpx.Response(
                400,
                request=httpx.Request("POST", url),
                text="response_format json_schema is unsupported",
            )
        return _success(
            url,
            json_module.dumps(
                {
                    "summary": "Grounded summary",
                    "basis": "tool:scan:1",
                    "risks_caveats": "Data may be incomplete.",
                    "tool_trace_summary": "scan executed",
                    "missing_data": [],
                    "grounded_source_refs": ["tool:scan:1"],
                    "claim_source_refs": {},
                    "research_metadata": {},
                }
            ),
        )

    json_module = json
    monkeypatch.setattr(httpx, "post", fake_post)

    _, usage = _client().chat(
        [{"role": "user", "content": "synthesize"}],
        response_schema=SYNTHESIS_RESPONSE_SCHEMA,
        stage="synthesize",
    )

    assert [payload["response_format"]["type"] for payload in payloads] == [
        "json_schema",
        "json_object",
    ]
    assert usage["structured_output_mode"] == "json_object"
    assert usage["structured_output_downgraded"] is True


def test_unrelated_http_400_does_not_trigger_schema_downgrade(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_LLM_API_KEY", "test")
    payloads: list[dict] = []

    def fake_post(url, *, json, headers, timeout):
        del headers, timeout
        payloads.append(copy.deepcopy(json))
        return httpx.Response(
            400,
            request=httpx.Request("POST", url),
            text="invalid request payload",
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(LLMResponseError, match="LLM HTTP 400"):
        _client().chat(
            [{"role": "user", "content": "classify"}],
            response_schema=INTENT_CLASSIFICATION_SCHEMA,
            stage="classify",
        )

    assert len(payloads) == 1
    assert payloads[0]["response_format"]["type"] == "json_schema"


def test_strict_schema_does_not_add_transport_retry_budget(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_LLM_API_KEY", "test")
    calls = 0

    def fake_post(url, *, json, headers, timeout):
        nonlocal calls
        del json, headers, timeout
        calls += 1
        raise httpx.ReadTimeout("timeout", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(LLMTimeoutError, match="failed after 1 attempt"):
        _client().chat(
            [{"role": "user", "content": "classify"}],
            response_schema=INTENT_CLASSIFICATION_SCHEMA,
            stage="classify",
        )

    assert calls == 1
