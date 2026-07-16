"""Bounded assistant LLM startup preflight (issue #165).

The MVP1 contract treats the AI layer as an optional but *operationally
predictable* single verified model route. This module verifies that route
before natural-language chat is offered, and returns a typed, redaction-safe
result so callers can:

* fail startup/chat readiness with an actionable diagnostic, distinguishing
  missing configuration, an unreachable gateway, an authentication failure, a
  missing model and an unsupported structured-output capability;
* keep deterministic slash/data commands available in degraded mode and mark
  natural-language AI as unavailable;
* surface the actual successful route identity in operator status and traces
  without leaking secrets or prompt content.

It mirrors the fail-closed, bounded, typed shape of the Docker sandbox
preflight (``sandbox/docker_runtime.py``). The network probe is injectable so
tests drive it with a fake gateway; no live provider call is ever required.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Callable

from vnalpha.assistant.errors import (
    LLMConfigError,
    LLMGatewayError,
    LLMNoCompatibleFallbackError,
    LLMResponseError,
    LLMTimeoutError,
)

# A minimal structured probe: the smallest strict json_schema request that
# exercises the required JSON_SCHEMA capability end to end. It carries no user
# or prompt content beyond a fixed health token.
_PROBE_SCHEMA: dict = {
    "type": "json_schema",
    "json_schema": {
        "name": "assistant_preflight_probe",
        "schema": {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
    },
}
_PROBE_MESSAGES: list[dict] = [
    {"role": "user", "content": 'Reply with {"ok": true}.'},
]


class LLMPreflightCode(StrEnum):
    """Machine-readable, redaction-safe assistant preflight outcomes."""

    READY = "ready"
    MISSING_CONFIG = "missing_config"
    AUTH_NOT_CONFIGURED = "auth_not_configured"
    MISSING_MODEL = "missing_model"
    UNREACHABLE_GATEWAY = "unreachable_gateway"
    AUTH_FAILED = "auth_failed"
    MODEL_NOT_FOUND = "model_not_found"
    UNSUPPORTED_STRUCTURED_OUTPUT = "unsupported_structured_output"
    PROBE_FAILED = "probe_failed"


_REMEDIATION: dict[LLMPreflightCode, str] = {
    LLMPreflightCode.MISSING_CONFIG: (
        "Set VNALPHA_LLM_ENDPOINT and VNALPHA_MODEL_DEFAULT (or VNALPHA_LLM_MODEL)."
    ),
    LLMPreflightCode.AUTH_NOT_CONFIGURED: (
        "Set VNALPHA_LLM_API_KEY for the deployed gateway."
    ),
    LLMPreflightCode.MISSING_MODEL: (
        "Configure a valid model alias and its declared capabilities."
    ),
    LLMPreflightCode.UNREACHABLE_GATEWAY: (
        "Verify the gateway endpoint is deployed and reachable from this host."
    ),
    LLMPreflightCode.AUTH_FAILED: (
        "Check that VNALPHA_LLM_API_KEY is valid for the deployed gateway."
    ),
    LLMPreflightCode.MODEL_NOT_FOUND: (
        "Confirm the configured model alias is visible on the gateway."
    ),
    LLMPreflightCode.UNSUPPORTED_STRUCTURED_OUTPUT: (
        "Use a model route that supports structured (json_schema) output."
    ),
    LLMPreflightCode.PROBE_FAILED: (
        "Inspect gateway logs; the structured probe returned an unexpected result."
    ),
}


@dataclass(frozen=True, slots=True)
class LLMPreflightResult:
    """Typed, redaction-safe outcome of one assistant preflight."""

    code: LLMPreflightCode
    detail: str
    model: str | None = None
    endpoint: str | None = None
    route: dict | None = field(default=None)

    @property
    def ready(self) -> bool:
        return self.code is LLMPreflightCode.READY

    @property
    def remediation(self) -> str | None:
        return _REMEDIATION.get(self.code)

    def to_status_dict(self) -> dict[str, object]:
        """A secret-free, prompt-free status view for operators and traces."""
        return {
            "ready": self.ready,
            "code": self.code.value,
            "detail": self.detail,
            "model": self.model,
            "endpoint": self.endpoint,
            "route": self.route,
            "remediation": self.remediation,
        }


# A gateway probe is any callable that performs one bounded structured chat and
# returns the successful route identity dict. Injectable for tests.
GatewayProbe = Callable[[], dict | None]


def run_llm_preflight(
    *,
    probe: GatewayProbe | None = None,
    api_key: str | None = None,
) -> LLMPreflightResult:
    """Verify the single MVP1 model route without leaking secrets or prompts.

    Args:
        probe: Optional injected structured-probe callable returning the route
            identity dict (used by tests). When ``None`` a real bounded gateway
            probe is constructed from the environment configuration.
        api_key: Optional explicit API key; defaults to ``VNALPHA_LLM_API_KEY``.

    Returns:
        A typed :class:`LLMPreflightResult`. Never raises for an expected
        failure mode — every outcome is a typed code.
    """

    from vnalpha.assistant.gateway import LLMGatewayConfig

    config = LLMGatewayConfig.from_env()
    try:
        config.validate()
    except LLMConfigError as exc:
        return LLMPreflightResult(
            LLMPreflightCode.MISSING_CONFIG,
            str(exc),
            model=config.model or None,
            endpoint=config.endpoint or None,
        )

    resolved_key = (
        api_key if api_key is not None else os.environ.get("VNALPHA_LLM_API_KEY", "")
    ).strip()
    if not resolved_key:
        return LLMPreflightResult(
            LLMPreflightCode.AUTH_NOT_CONFIGURED,
            "VNALPHA_LLM_API_KEY is not set; natural-language chat is unavailable.",
            model=config.model,
            endpoint=config.endpoint,
        )

    if probe is None:
        probe = _default_probe(config)

    try:
        route = probe()
    except LLMConfigError as exc:
        # Routing/model configuration is invalid (no built-in model, bad alias).
        return LLMPreflightResult(
            LLMPreflightCode.MISSING_MODEL,
            str(exc),
            model=config.model,
            endpoint=config.endpoint,
        )
    except LLMNoCompatibleFallbackError as exc:
        # The strict route failed and no compatible fallback exists. If the
        # underlying primary failure was itself a transport/timeout or an
        # HTTP-shaped error, classify by that real cause rather than masking it
        # as a structured-output gap.
        primary = exc.primary_error
        if isinstance(primary, LLMTimeoutError):
            return LLMPreflightResult(
                LLMPreflightCode.UNREACHABLE_GATEWAY,
                str(primary),
                model=config.model,
                endpoint=config.endpoint,
            )
        if isinstance(primary, LLMResponseError):
            return _classify_response_error(primary, config)
        return LLMPreflightResult(
            LLMPreflightCode.UNSUPPORTED_STRUCTURED_OUTPUT,
            str(exc),
            model=config.model,
            endpoint=config.endpoint,
        )
    except LLMTimeoutError as exc:
        return LLMPreflightResult(
            LLMPreflightCode.UNREACHABLE_GATEWAY,
            str(exc),
            model=config.model,
            endpoint=config.endpoint,
        )
    except LLMResponseError as exc:
        return _classify_response_error(exc, config)
    except LLMGatewayError as exc:
        return LLMPreflightResult(
            LLMPreflightCode.PROBE_FAILED,
            str(exc),
            model=config.model,
            endpoint=config.endpoint,
        )

    return LLMPreflightResult(
        LLMPreflightCode.READY,
        f"Verified structured route for model '{config.model}'.",
        model=config.model,
        endpoint=config.endpoint,
        route=route,
    )


def _classify_response_error(exc: LLMResponseError, config) -> LLMPreflightResult:
    """Map an HTTP-shaped gateway error to a typed preflight code by status."""
    text = str(exc)
    status = _status_code_from_error(text)
    if status in {401, 403}:
        code = LLMPreflightCode.AUTH_FAILED
    elif status == 404:
        code = LLMPreflightCode.MODEL_NOT_FOUND
    elif status == 400 and _schema_unsupported(text):
        code = LLMPreflightCode.UNSUPPORTED_STRUCTURED_OUTPUT
    elif status is not None and status >= 500:
        code = LLMPreflightCode.UNREACHABLE_GATEWAY
    else:
        code = LLMPreflightCode.PROBE_FAILED
    return LLMPreflightResult(
        code,
        text,
        model=config.model,
        endpoint=config.endpoint,
    )


def _schema_unsupported(text: str) -> bool:
    """Detect a gateway 400 that rejects structured (json_schema) output."""
    from vnalpha.assistant.gateway import _SCHEMA_UNSUPPORTED_MARKERS

    lowered = text.lower()
    return any(marker in lowered for marker in _SCHEMA_UNSUPPORTED_MARKERS)


def _status_code_from_error(text: str) -> int | None:
    """Extract the HTTP status from an ``LLM HTTP <code>: ...`` message."""
    marker = "LLM HTTP "
    index = text.find(marker)
    if index == -1:
        return None
    tail = text[index + len(marker) :].lstrip()
    digits = ""
    for char in tail:
        if char.isdigit():
            digits += char
        else:
            break
    return int(digits) if digits else None


def _default_probe(config) -> GatewayProbe:
    """Build the real bounded structured probe from environment configuration."""

    def probe() -> dict | None:
        from vnalpha.assistant.gateway import LLMGatewayClient

        client = LLMGatewayClient(config)
        _content, usage = client.chat(
            _PROBE_MESSAGES,
            response_schema=_PROBE_SCHEMA,
            stage="preflight",
        )
        route = usage.get("model_route") if isinstance(usage, dict) else None
        return route if isinstance(route, dict) else None

    return probe


__all__ = [
    "LLMPreflightCode",
    "LLMPreflightResult",
    "run_llm_preflight",
]
