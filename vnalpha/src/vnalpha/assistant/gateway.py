from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


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


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

ASSISTANT_MODEL_DEFAULT = "oc-gpt-5.4-mini"
ASSISTANT_ENDPOINT_DEFAULT = "https://api.openai.com/v1/chat/completions"
ASSISTANT_TIMEOUT_DEFAULT = 30
ASSISTANT_MAX_OUTPUT_TOKENS_DEFAULT = 16000
ASSISTANT_MAX_RETRIES_DEFAULT = 2
ASSISTANT_STORE_RAW_DEFAULT = False  # disabled by default


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class LLMGatewayConfig:
    model: str
    endpoint: str
    timeout: int
    max_output_tokens: int
    max_retries: int
    store_raw: bool  # if True, raw prompt/response stored; else None

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def redact_summary(text: str | None, max_chars: int = 200) -> str | None:
    """Redact/truncate for trace summary storage (no sensitive keys)."""
    if text is None:
        return None
    if len(text) > max_chars:
        return text[:max_chars] + "...[redacted]"
    return text


# ---------------------------------------------------------------------------
# Production client
# ---------------------------------------------------------------------------


class LLMGatewayClient:
    """Thin HTTP client for LLM calls. Never called directly from tools — only from assistant."""

    def __init__(self, config: LLMGatewayConfig | None = None) -> None:
        self._config = config or LLMGatewayConfig.from_env()

    def chat(
        self,
        messages: list[dict],
        response_schema: dict | None = None,
        *,
        stage: str = "unknown",
        task_type: str | None = None,
        model_profile: str | None = None,
        route_metadata: Mapping[str, str] | None = None,
    ) -> tuple[str, dict]:
        """Send a chat completion request.

        Returns (response_text, usage_dict).
        Raises LLMGatewayError on failure.
        """
        import httpx

        from vnalpha.assistant.errors import (
            LLMConfigError,
            LLMResponseError,
            LLMTimeoutError,
        )

        api_key = os.environ.get("VNALPHA_LLM_API_KEY") or os.environ.get(
            "OPENAI_API_KEY", ""
        )

        # Early validation — avoid httpx LocalProtocolError on empty Bearer token
        if not api_key or not api_key.strip():
            err = LLMConfigError(
                "LLM API key is not set. "
                "Set VNALPHA_LLM_API_KEY (or OPENAI_API_KEY) in your environment or .env file."
            )
            _log_llm_error(stage, err)
            raise err

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": self._config.model,
            "messages": messages,
            "max_tokens": self._config.max_output_tokens,
        }
        if response_schema:
            payload["response_format"] = {"type": "json_object"}

        last_exc: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                resp = httpx.post(
                    self._config.endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self._config.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return content, usage
            except httpx.TimeoutException as exc:
                last_exc = exc
            except httpx.HTTPStatusError as exc:
                err = LLMResponseError(
                    f"LLM HTTP {exc.response.status_code}: {exc.response.text[:200]}"
                )
                _log_llm_error(stage, err, attempt=attempt)
                raise err from exc
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        timeout_err = LLMTimeoutError(
            f"LLM call failed after {self._config.max_retries + 1} attempts"
        )
        _log_llm_error(stage, timeout_err, cause=last_exc)
        raise timeout_err from last_exc

    @property
    def config(self) -> LLMGatewayConfig:
        return self._config


# ---------------------------------------------------------------------------
# Test stub
# ---------------------------------------------------------------------------


class FakeLLMClient:
    """Deterministic stub for tests. Returns pre-configured responses."""

    def __init__(self, responses: list[tuple[str, dict]] | None = None) -> None:
        self._responses = list(responses or [])
        self._call_count = 0
        self.calls: list[list[dict]] = []

    def chat(
        self,
        messages: list[dict],
        response_schema: dict | None = None,
        *,
        stage: str = "unknown",
        task_type: str | None = None,
        model_profile: str | None = None,
        route_metadata: Mapping[str, str] | None = None,
    ) -> tuple[str, dict]:
        self.calls.append(messages)
        if self._responses:
            idx = min(self._call_count, len(self._responses) - 1)
            resp = self._responses[idx]
            self._call_count += 1
            return resp
        return (
            '{"intent": "scan_candidates", "confidence": 0.95, "entities": {}}',
            {},
        )
