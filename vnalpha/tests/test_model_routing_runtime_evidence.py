from __future__ import annotations

from types import MappingProxyType

import httpx

from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig
from vnalpha.model_routing import ModelOverrideStore, ModelProfile, ModelRoutingConfig


def _routing_config() -> ModelRoutingConfig:
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
                ModelProfile.REASONING: (ModelProfile.DEFAULT,),
                ModelProfile.LONG_CONTEXT: (ModelProfile.REASONING,),
            }
        ),
    )


def test_gateway_fallback_emits_explicit_audit_events(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VNALPHA_LLM_API_KEY", "test-key")
    captured: list[str] = []

    def fake_log_audit(event_type, summary, **kwargs):
        del summary, kwargs
        captured.append(event_type)

    def fake_post(url, *, json, headers, timeout):
        del headers, timeout
        request = httpx.Request("POST", url)
        if json["model"] == "reasoning-model":
            return httpx.Response(404, request=request, text="model unavailable")
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1},
            },
        )

    monkeypatch.setattr("vnalpha.observability.audit.log_audit", fake_log_audit)
    monkeypatch.setattr(httpx, "post", fake_post)
    client = LLMGatewayClient(
        LLMGatewayConfig(
            model="default-model",
            endpoint="https://llm.example.test/v1/chat/completions",
            timeout=1,
            max_output_tokens=256,
            max_retries=0,
            store_raw=False,
        ),
        routing_config=_routing_config(),
        override_store=ModelOverrideStore(workspace_root=tmp_path),
    )

    client.chat(
        [{"role": "user", "content": "analyze"}],
        stage="synthesize",
        task_type="deep_symbol_analysis",
    )

    assert captured == [
        "MODEL_ROUTE_SELECTED",
        "MODEL_CALL_STARTED",
        "MODEL_CALL_FAILED",
        "MODEL_FALLBACK_USED",
        "MODEL_CALL_STARTED",
        "MODEL_CALL_SUCCEEDED",
    ]
