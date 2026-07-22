from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from vnalpha.assistant.errors import (
    LLMConfigError,
    LLMGatewayError,
    LLMNoCompatibleFallbackError,
    LLMResponseError,
    LLMTimeoutError,
)
from vnalpha.model_routing.config import ModelRoutingConfig
from vnalpha.model_routing.integration import GatewayRouteRequest, resolve_gateway_route
from vnalpha.model_routing.models import (
    ModelCapability,
    ModelProfile,
    ModelRouteDecision,
)
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
    response_content_chars: int | None = None,
    finish_reason: str | None = None,
) -> None:
    try:
        log = structlog.get_logger("assistant.gateway")
        log.error(
            "LLM call failed",
            stage=stage,
            error_type=type(exc).__name__,
            attempt=attempt,
            cause_type=type(cause).__name__ if cause else None,
            response_content_chars=response_content_chars,
            finish_reason=finish_reason,
        )
    except Exception:  # noqa: BLE001
        pass


ASSISTANT_MODEL_DEFAULT = ""
ASSISTANT_ENDPOINT_DEFAULT = ""
ASSISTANT_TIMEOUT_DEFAULT = 30
ASSISTANT_MAX_OUTPUT_TOKENS_DEFAULT = 16000
ASSISTANT_MAX_RETRIES_DEFAULT = 0
ASSISTANT_STORE_RAW_DEFAULT = False
_SCHEMA_UNSUPPORTED_MARKERS = (
    "json_schema",
    "response_format",
    "structured output",
    "structured_output",
    "unsupported schema",
)
RETRY_AFTER_MAX_SECONDS = 300


def _integer_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise LLMConfigError(f"{name} must be an integer.") from exc


def _schema_name(schema: Mapping[str, Any]) -> str:
    candidate = str(schema.get("title") or schema.get("$id") or "vnalpha_response")
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", candidate).strip("_")
    return (cleaned or "vnalpha_response")[:64]


def _response_format(response_schema: dict[str, Any]) -> dict[str, Any]:
    if response_schema == {"type": "json_object"}:
        return {"type": "json_object"}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": _schema_name(response_schema),
            "strict": True,
            "schema": response_schema,
        },
    }


def _schema_format_unsupported(status_code: int, response_text: str) -> bool:
    if status_code != 400:
        return False
    lowered = response_text.lower()
    return any(marker in lowered for marker in _SCHEMA_UNSUPPORTED_MARKERS)


def _parse_gateway_error_type(payload_text: str) -> str | None:
    try:
        payload = json.loads(payload_text)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, dict):
        raw = error.get("type")
    else:
        raw = payload.get("type")
    if isinstance(raw, str):
        return raw.strip() or None
    return None


def _parse_retry_after(raw: str | None) -> int | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    if value <= 0:
        return None
    return min(value, RETRY_AFTER_MAX_SECONDS)


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
        model = (
            os.environ.get("VNALPHA_MODEL_DEFAULT", "").strip()
            or os.environ.get("VNALPHA_LLM_MODEL", ASSISTANT_MODEL_DEFAULT).strip()
        )
        config = cls(
            model=model,
            endpoint=os.environ.get(
                "VNALPHA_LLM_ENDPOINT", ASSISTANT_ENDPOINT_DEFAULT
            ).strip(),
            timeout=_integer_env("VNALPHA_LLM_TIMEOUT", ASSISTANT_TIMEOUT_DEFAULT),
            max_output_tokens=_integer_env(
                "VNALPHA_LLM_MAX_OUTPUT_TOKENS",
                ASSISTANT_MAX_OUTPUT_TOKENS_DEFAULT,
            ),
            max_retries=_integer_env(
                "VNALPHA_LLM_MAX_RETRIES", ASSISTANT_MAX_RETRIES_DEFAULT
            ),
            store_raw=os.environ.get("VNALPHA_LLM_STORE_RAW", "").lower()
            in ("1", "true", "yes"),
        )
        return config

    def validate(self) -> None:
        missing: list[str] = []
        if not self.endpoint.strip():
            missing.append("VNALPHA_LLM_ENDPOINT")
        if not self.model.strip():
            missing.append("VNALPHA_MODEL_DEFAULT or VNALPHA_LLM_MODEL")
        if missing:
            raise LLMConfigError(
                "LLM assistant is disabled because explicit configuration is missing: "
                + ", ".join(missing)
                + "."
            )

        parsed = urlparse(self.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise LLMConfigError(
                "VNALPHA_LLM_ENDPOINT must be an explicit http:// or https:// URL."
            )
        try:
            _parsed_port = parsed.port
        except ValueError as exc:
            raise LLMConfigError(
                "VNALPHA_LLM_ENDPOINT must contain a valid numeric port."
            ) from exc
        if parsed.username is not None or parsed.password is not None:
            raise LLMConfigError("VNALPHA_LLM_ENDPOINT must not contain userinfo.")
        hostname = parsed.hostname or ""
        is_loopback = hostname.lower() == "localhost"
        if not is_loopback:
            try:
                is_loopback = ip_address(hostname).is_loopback
            except ValueError:
                is_loopback = False
        if parsed.scheme == "http" and not is_loopback:
            raise LLMConfigError(
                "VNALPHA_LLM_ENDPOINT must use HTTPS outside the local loopback host."
            )
        if self.timeout <= 0:
            raise LLMConfigError("VNALPHA_LLM_TIMEOUT must be greater than zero.")
        if self.max_output_tokens <= 0:
            raise LLMConfigError(
                "VNALPHA_LLM_MAX_OUTPUT_TOKENS must be greater than zero."
            )
        if self.max_retries < 0:
            raise LLMConfigError("VNALPHA_LLM_MAX_RETRIES must not be negative.")


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
        api_key: str | None = None,
        routing_config: ModelRoutingConfig | None = None,
        override_store: ModelOverrideStore | None = None,
    ) -> None:
        self._config = config or LLMGatewayConfig.from_env()
        self._config.validate()
        self._api_key = api_key
        try:
            self._routing_config = routing_config or ModelRoutingConfig.from_env(
                default_model_id=self._config.model
            )
        except ValueError as exc:
            raise LLMConfigError(f"Invalid model routing configuration: {exc}") from exc
        self._override_store = override_store or DEFAULT_OVERRIDE_STORE
        self._last_route_decision: ModelRouteDecision | None = None
        self._last_raw_responses: list[dict[str, Any]] = []

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
        api_key = (
            self._api_key
            if self._api_key is not None
            else os.environ.get("VNALPHA_LLM_API_KEY", "")
        ).strip()
        if not api_key:
            err = LLMConfigError(
                "LLM assistant is disabled because VNALPHA_LLM_API_KEY is not set. "
                "OPENAI_API_KEY is intentionally not used as an implicit fallback."
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
        self._last_raw_responses = []
        strict_schema = bool(
            response_schema and response_schema != {"type": "json_object"}
        )
        required_capability = ModelCapability.JSON_SCHEMA if strict_schema else None
        compatible_fallbacks = fallback_route_decisions(
            self._routing_config,
            primary,
            required_capability=required_capability,
        )
        routes = (primary, *compatible_fallbacks)
        previous: ModelRouteDecision | None = None
        last_error: Exception | None = None

        for decision in routes:
            if previous is not None:
                emit_fallback_used(previous, decision, safe_metadata)
            self._last_route_decision = decision
            set_last_route_decision(decision)
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
            usage_payload = dict(usage)
            usage_payload["model_route"] = decision.to_dict()
            return content, usage_payload

        if strict_schema and last_error is not None and not compatible_fallbacks:
            if isinstance(last_error, LLMResponseError) and not (
                last_error.error_kind == "structured_output_unsupported"
                or last_error.status_code == 404
            ):
                raise last_error
            compatibility_error = LLMNoCompatibleFallbackError(
                stage=stage,
                primary_model=primary.model_id,
                required_capability=ModelCapability.JSON_SCHEMA.value,
                primary_error=last_error,
            )
            _log_llm_error(stage, compatibility_error, cause=last_error)
            raise compatibility_error from last_error
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
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": decision.model_id,
            "messages": messages,
            "max_tokens": self._config.max_output_tokens,
        }
        structured_mode = "none"
        if response_schema:
            payload["response_format"] = _response_format(response_schema)
            structured_mode = payload["response_format"]["type"]

        emit_call_started(decision, route_metadata)
        started = time.monotonic()
        last_transport_error: Exception | None = None
        schema_downgraded = False
        retry_attempt = 0
        call_count = 0
        while retry_attempt <= self._config.max_retries:
            response_content_chars: int | None = None
            finish_reason: str | None = None
            call_count += 1
            try:
                response = httpx.post(
                    self._config.endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self._config.timeout,
                )
                if self._config.store_raw:
                    self._last_raw_responses.append(
                        {
                            "route_profile": decision.profile.value,
                            "status_code": response.status_code,
                            "response_chars": len(response.text),
                        }
                    )
                response.raise_for_status()
                data = response.json()
                choice = data["choices"][0]
                content = choice["message"]["content"]
                raw_finish_reason = choice.get("finish_reason")
                if isinstance(raw_finish_reason, str):
                    finish_reason = raw_finish_reason
                if not isinstance(content, str):
                    raise LLMResponseError(
                        "LLM response from model "
                        f"'{decision.model_id}' has no textual completion content."
                    )
                response_content_chars = len(content)
                if not content.strip():
                    raise LLMResponseError(
                        "LLM response from model "
                        f"'{decision.model_id}' has empty completion content."
                    )
                usage = data.get("usage", {})
                usage_payload = dict(usage) if isinstance(usage, dict) else {}
                usage_payload["structured_output_mode"] = structured_mode
                usage_payload["structured_output_downgraded"] = schema_downgraded
                latency_ms = (time.monotonic() - started) * 1000
                emit_call_succeeded(
                    decision,
                    latency_ms=latency_ms,
                    usage=usage_payload,
                    response_content_chars=response_content_chars,
                    finish_reason=finish_reason,
                    metadata=route_metadata,
                )
                return content, usage_payload
            except httpx.TimeoutException as exc:
                last_transport_error = exc
                if retry_attempt < self._config.max_retries:
                    retry_attempt += 1
                    continue
                break
            except httpx.RequestError as exc:
                last_transport_error = exc
                if retry_attempt < self._config.max_retries:
                    retry_attempt += 1
                    continue
                break
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if (
                    response_schema
                    and structured_mode == "json_schema"
                    and not schema_downgraded
                    and _schema_format_unsupported(status_code, exc.response.text)
                ):
                    payload["response_format"] = {"type": "json_object"}
                    structured_mode = "json_object"
                    schema_downgraded = True
                    continue
                error = LLMResponseError(
                    f"LLM HTTP {status_code}.",
                    status_code=status_code,
                    error_kind=(
                        "structured_output_unsupported"
                        if status_code == 400
                        and _schema_format_unsupported(status_code, exc.response.text)
                        else "http_error"
                    ),
                    error_type=_parse_gateway_error_type(exc.response.text),
                    retry_after_seconds=_parse_retry_after(
                        exc.response.headers.get("retry-after")
                    ),
                )
                fallbackable = (
                    status_code in {400, 404, 408, 409, 429} or status_code >= 500
                )
                retryable = status_code in {408, 429} or status_code >= 500
                if status_code == 503:
                    retryable = False
                if retryable and retry_attempt < self._config.max_retries:
                    retry_attempt += 1
                    continue
                latency_ms = (time.monotonic() - started) * 1000
                emit_call_failed(
                    decision,
                    error,
                    latency_ms=latency_ms,
                    metadata=route_metadata,
                )
                _log_llm_error(decision.stage, error, attempt=retry_attempt)
                if fallbackable:
                    raise _FallbackableCallError(error) from exc
                raise error from exc
            except LLMResponseError as exc:
                latency_ms = (time.monotonic() - started) * 1000
                emit_call_failed(
                    decision,
                    exc,
                    latency_ms=latency_ms,
                    response_content_chars=response_content_chars,
                    finish_reason=finish_reason,
                    metadata=route_metadata,
                )
                _log_llm_error(
                    decision.stage,
                    exc,
                    attempt=retry_attempt,
                    response_content_chars=response_content_chars,
                    finish_reason=finish_reason,
                )
                raise _FallbackableCallError(exc) from exc
            except (KeyError, TypeError, ValueError) as exc:
                error = LLMResponseError(
                    f"Malformed LLM response from model '{decision.model_id}': {exc}"
                )
                latency_ms = (time.monotonic() - started) * 1000
                emit_call_failed(
                    decision,
                    error,
                    latency_ms=latency_ms,
                    response_content_chars=response_content_chars,
                    finish_reason=finish_reason,
                    metadata=route_metadata,
                )
                _log_llm_error(
                    decision.stage,
                    error,
                    attempt=retry_attempt,
                    response_content_chars=response_content_chars,
                    finish_reason=finish_reason,
                )
                raise _FallbackableCallError(error) from exc

        timeout_error = LLMTimeoutError(
            f"Model '{decision.model_id}' failed after {call_count} attempt(s)."
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

    @property
    def last_raw_responses(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(response) for response in self._last_raw_responses)


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

    @property
    def last_raw_responses(self) -> tuple[dict[str, Any], ...]:
        return ()
