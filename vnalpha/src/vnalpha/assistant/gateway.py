from __future__ import annotations

import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from vnalpha.model_routing.config import ModelRoutingConfig
from vnalpha.model_routing.integration import GatewayRouteRequest, resolve_gateway_route
from vnalpha.model_routing.models import ModelProfile, ModelRouteDecision
from vnalpha.model_routing.observability import (
    emit_call_failed,
    emit_call_started,
    emit_call_succeeded,
    emit_fallback_used,
    emit_route_selected,
    redact_route_metadata,
)
from vnalpha.model_routing.overrides import DEFAULT_OVERRIDE_STORE, ModelOverrideStore
from vnalpha.model_routing.resolver import fallback_route_decisions
from vnalpha.model_routing.runtime import set_last_route_decision


def _log_llm_error(
    stage: str,
    exc: Exception,
    *,
    attempt: int | None = None,
    cause: Exception | None = None,
) -> None:
    try:
        import structlog

        log = structlog.get_logger("assistant.gateway")
        log.error(
            "LLM call failed",
            stage=stage,
            error_type=type(exc).__name__,
            error=str(exc),
            attempt=attempt,
            cause=str(cause) if cause else None,
        )
    except Exception:  # noqa: BLE001
        pass


ASSISTANT_MODEL_DEFAULT = "oc-gpt-5.4-mini"
ASSISTANT_ENDPOINT_DEFAULT = "https://api.openai.com/v1/chat/completions"
ASSISTANT_TIMEOUT_DEFAULT = 30
ASSISTANT_MAX_OUTPUT_TOKENS_DEFAULT = 16000
ASSISTANT_MAX_RETRIES_DEFAULT = 2
ASSISTANT_STORE_RAW_DEFAULT = False


@dataclass
class LLMGatewayConfig:
    model: str
    endpoint: str
    timeout: int
    max_output_tokens: int
    max_retries: int
    store_raw: bool

    @classmethod
    def from_env(cls) -> LLMGatewayConfig:
        return cls(
            model=os.environ.get("VNALPHA_LLM_MODEL", ASSISTANT_MODEL_DEFAULT),
            endpoint=os.environ.get("VNALPHA_LLM_ENDPOINT", ASSISTANT_ENDPOINT_DEFAULT),
            timeout=int(
                os.environ.get("VNALPHA_LLM_TIMEOUT", ASSISTANT_TIMEOUT_DEFAULT)
            ),
            max_output_tokens=int(
                os.environ.get(
                    "VNALPHA_LLM_MAX_OUTPUT_TOKENS",
                    ASSISTANT_MAX_OUTPUT_TOKENS_DEFAULT,
                )
            ),
            max_retries=int(
                os.environ.get("VNALPHA_LLM_MAX_RETRIES", ASSISTANT_MAX_RETRIES_DEFAULT)
            ),
            store_raw=os.environ.get("VNALPHA_LLM_STORE_RAW", "").lower()
            in ("1", "true", "yes"),
        )


def redact_summary(text: str | None, max_chars: int = 200) -> str | None:
    if text is None:
        return None
    if len(text) > max_chars:
        return text[:max_chars] + "...[redacted]"
    return text


class _FallbackableCallError(Exception):
    def __init__(self, error: Exception) -> None:
        super().__init__(str(error))
        self.error = error


class LLMGatewayClient:
    """HTTP LLM client with deterministic profile routing and explicit fallback."""

    def __init__(
        self,
        config: LLMGatewayConfig | None = None,
        *,
        routing_config: ModelRoutingConfig | None = None,
        override_store: ModelOverrideStore | None = None,
    ) -> None:
        self._config = config or LLMGatewayConfig.from_env()
        self._routing_config = routing_config or ModelRoutingConfig.from_env(
            default_model_id=self._config.model
        )
        self._override_store = override_store or DEFAULT_OVERRIDE_STORE
        self._last_route_decision: ModelRouteDecision | None = None

    def resolve_route(
        self,
        *,
        stage: str,
        task_type: str | None = None,
        model_profile: ModelProfile | str | None = None,
        route_metadata: Mapping[str, Any] | None = None,
    ) -> ModelRouteDecision:
        session_value = route_metadata.get("session_id") if route_metadata else None
        session_id = session_value if isinstance(session_value, str) else None
        return resolve_gateway_route(
            self._routing_config,
            GatewayRouteRequest(
                stage=stage,
                task_type=task_type,
                model_profile=model_profile,
                route_metadata=route_metadata,
                override=self._override_store.get_current_override(
                    session_id=session_id
                ),
            ),
        )

    def chat(
        self,
        messages: list[dict],
        response_schema: dict | None = None,
        *,
        stage: str = "unknown",
        task_type: str | None = None,
        model_profile: ModelProfile | str | None = None,
        route_metadata: Mapping[str, Any] | None = None,
    ) -> tuple[str, dict]:
        from vnalpha.assistant.errors import LLMConfigError, LLMGatewayError

        api_key = os.environ.get("VNALPHA_LLM_API_KEY") or os.environ.get(
            "OPENAI_API_KEY", ""
        )
        if not api_key or not api_key.strip():
            err = LLMConfigError(
                "LLM API key is not set. "
                "Set VNALPHA_LLM_API_KEY (or OPENAI_API_KEY) in your environment or .env file."
            )
            _log_llm_error(stage, err)
            raise err

        try:
            primary = self.resolve_route(
                stage=stage,
                task_type=task_type,
                model_profile=model_profile,
                route_metadata=route_metadata,
            )
        except ValueError as exc:
            raise LLMConfigError(str(exc)) from exc

        safe_metadata = redact_route_metadata(route_metadata or {})
        emit_route_selected(primary, safe_metadata)
        routes = (primary, *fallback_route_decisions(self._routing_config, primary))
        previous: ModelRouteDecision | None = None
        last_error: Exception | None = None

        for decision in routes:
            if previous is not None:
                emit_fallback_used(previous, decision, safe_metadata)
            try:
                content, usage = self._call_model(
                    decision,
                    messages,
                    response_schema=response_schema,
                    api_key=api_key,
                    route_metadata=safe_metadata,
                )
            except _FallbackableCallError as exc:
                last_error = exc.error
                previous = decision
                continue
            self._last_route_decision = decision
            set_last_route_decision(decision)
            usage_payload = dict(usage)
            usage_payload["model_route"] = decision.to_dict()
            return content, usage_payload

        if isinstance(last_error, LLMGatewayError):
            raise last_error
        fallback_error = LLMGatewayError(
            f"All configured model routes failed for stage '{stage}'."
        )
        _log_llm_error(stage, fallback_error, cause=last_error)
        raise fallback_error from last_error

    def _call_model(
        self,
        decision: ModelRouteDecision,
        messages: list[dict],
        *,
        response_schema: dict | None,
        api_key: str,
        route_metadata: Mapping[str, Any],
    ) -> tuple[str, dict]:
        import httpx

        from vnalpha.assistant.errors import LLMResponseError, LLMTimeoutError

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": decision.model_id,
            "messages": messages,
            "max_tokens": self._config.max_output_tokens,
        }
        if response_schema:
            payload["response_format"] = {"type": "json_object"}

        emit_call_started(decision, route_metadata)
        started = time.monotonic()
        last_transport_error: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                response = httpx.post(
                    self._config.endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self._config.timeout,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                latency_ms = (time.monotonic() - started) * 1000
                emit_call_succeeded(
                    decision,
                    latency_ms=latency_ms,
                    usage=usage,
                    metadata=route_metadata,
                )
                return content, dict(usage) if isinstance(usage, dict) else {}
            except httpx.TimeoutException as exc:
                last_transport_error = exc
                if attempt < self._config.max_retries:
                    continue
            except httpx.RequestError as exc:
                last_transport_error = exc
                if attempt < self._config.max_retries:
                    continue
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                error = LLMResponseError(
                    f"LLM HTTP {status_code}: {exc.response.text[:200]}"
                )
                fallbackable = (
                    status_code in {400, 404, 408, 409, 429} or status_code >= 500
                )
                retryable = status_code in {408, 409, 429} or status_code >= 500
                if retryable and attempt < self._config.max_retries:
                    continue
                latency_ms = (time.monotonic() - started) * 1000
                emit_call_failed(
                    decision,
                    error,
                    latency_ms=latency_ms,
                    metadata=route_metadata,
                )
                _log_llm_error(decision.stage, error, attempt=attempt)
                if fallbackable:
                    raise _FallbackableCallError(error) from exc
                raise error from exc
            except (KeyError, TypeError, ValueError) as exc:
                error = LLMResponseError(
                    f"Malformed LLM response from model '{decision.model_id}': {exc}"
                )
                latency_ms = (time.monotonic() - started) * 1000
                emit_call_failed(
                    decision,
                    error,
                    latency_ms=latency_ms,
                    metadata=route_metadata,
                )
                raise _FallbackableCallError(error) from exc

        timeout_error = LLMTimeoutError(
            f"Model '{decision.model_id}' failed after "
            f"{self._config.max_retries + 1} attempt(s)."
        )
        latency_ms = (time.monotonic() - started) * 1000
        emit_call_failed(
            decision,
            timeout_error,
            latency_ms=latency_ms,
            metadata=route_metadata,
        )
        _log_llm_error(decision.stage, timeout_error, cause=last_transport_error)
        raise _FallbackableCallError(timeout_error) from last_transport_error

    @property
    def config(self) -> LLMGatewayConfig:
        return self._config

    @property
    def routing_config(self) -> ModelRoutingConfig:
        return self._routing_config

    @property
    def last_route_decision(self) -> ModelRouteDecision | None:
        return self._last_route_decision


class FakeLLMClient:
    """Deterministic stub for tests with route metadata capture."""

    def __init__(self, responses: list[tuple[str, dict]] | None = None) -> None:
        self._responses = list(responses or [])
        self._call_count = 0
        self.calls: list[list[dict]] = []
        self.call_metadata: list[dict[str, Any]] = []
        self._last_route_decision: ModelRouteDecision | None = None

    def chat(
        self,
        messages: list[dict],
        response_schema: dict | None = None,
        *,
        stage: str = "unknown",
        task_type: str | None = None,
        model_profile: ModelProfile | str | None = None,
        route_metadata: Mapping[str, Any] | None = None,
    ) -> tuple[str, dict]:
        self.calls.append(messages)
        self.call_metadata.append(
            {
                "response_schema": response_schema,
                "stage": stage,
                "task_type": task_type,
                "model_profile": (
                    model_profile.value
                    if isinstance(model_profile, ModelProfile)
                    else model_profile
                ),
                "route_metadata": dict(route_metadata or {}),
            }
        )
        if self._responses:
            index = min(self._call_count, len(self._responses) - 1)
            response = self._responses[index]
            self._call_count += 1
            return response
        return (
            '{"intent": "scan_candidates", "confidence": 0.95, "entities": {}}',
            {},
        )

    @property
    def last_route_decision(self) -> ModelRouteDecision | None:
        return self._last_route_decision
