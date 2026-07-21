from __future__ import annotations

import copy

import httpx

from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig
from vnalpha.assistant.intent import INTENT_CLASSIFICATION_SCHEMA


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
