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

import json
import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Callable
from urllib.parse import urlsplit

from vnalpha.assistant.errors import (
    LLMConfigError,
    LLMGatewayError,
    LLMNoCompatibleFallbackError,
    LLMResponseError,
    LLMTimeoutError,
)
from vnalpha.core.text_safety import redact_structure, sanitize_text

# A minimal structured probe: the smallest strict json_schema request that
# exercises the required JSON_SCHEMA capability end to end. It carries no user
# or prompt content beyond a fixed health token.
#
# This is a bare JSON Schema object. LLMGatewayClient.chat() wraps it into the
# provider ``response_format`` envelope itself, so passing a full
# ``{"type": "json_schema", ...}`` envelope here would double-wrap the schema
# and be rejected by the gateway as an invalid schema.
_PROBE_SCHEMA: dict = {
    "type": "object",
    "title": "assistant_preflight_probe",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
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
    error_type: str | None = None
    retry_after_seconds: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "detail", sanitize_text(self.detail))
        if self.model is not None:
            object.__setattr__(self, "model", sanitize_text(self.model))
        if self.endpoint is not None:
            object.__setattr__(self, "endpoint", sanitize_text(self.endpoint))
        if self.route is not None:
            object.__setattr__(self, "route", redact_structure(self.route))
        if self.error_type is not None:
            object.__setattr__(self, "error_type", sanitize_text(self.error_type))

    @property
    def ready(self) -> bool:
        return self.code is LLMPreflightCode.READY

    @property
    def remediation(self) -> str | None:
        if (
            self.code is LLMPreflightCode.UNREACHABLE_GATEWAY
            and self.error_type == "model_unavailable"
        ):
            return (
                "Check the gateway health endpoint (/health/umbrella) and "
                "confirm the model route is healthy."
            )
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
            "error_type": self.error_type,
            "retry_after_seconds": self.retry_after_seconds,
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

    try:
        config = LLMGatewayConfig.from_env()
        config.validate()
    except LLMConfigError as exc:
        return LLMPreflightResult(
            LLMPreflightCode.MISSING_CONFIG,
            str(exc),
            model=(
                os.environ.get("VNALPHA_MODEL_DEFAULT", "").strip()
                or os.environ.get("VNALPHA_LLM_MODEL", "").strip()
                or None
            ),
            endpoint=_safe_endpoint(os.environ.get("VNALPHA_LLM_ENDPOINT")),
        )

    resolved_key = (
        api_key if api_key is not None else os.environ.get("VNALPHA_LLM_API_KEY", "")
    ).strip()
    if not resolved_key:
        return LLMPreflightResult(
            LLMPreflightCode.AUTH_NOT_CONFIGURED,
            "VNALPHA_LLM_API_KEY is not set; natural-language chat is unavailable.",
            model=config.model,
            endpoint=_safe_endpoint(config.endpoint),
        )

    if probe is None:
        probe = _default_probe(config, resolved_key)

    try:
        route = probe()
    except LLMConfigError:
        # Routing/model configuration is invalid (no built-in model, bad alias).
        return LLMPreflightResult(
            LLMPreflightCode.MISSING_MODEL,
            "The configured model route is invalid.",
            model=config.model,
            endpoint=_safe_endpoint(config.endpoint),
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
                "The LLM gateway timed out during the bounded preflight probe.",
                model=config.model,
                endpoint=_safe_endpoint(config.endpoint),
            )
        if isinstance(primary, LLMResponseError):
            return _classify_response_error(primary, config)
        return LLMPreflightResult(
            LLMPreflightCode.UNSUPPORTED_STRUCTURED_OUTPUT,
            "No configured route accepted the required structured output.",
            model=config.model,
            endpoint=_safe_endpoint(config.endpoint),
        )
    except LLMTimeoutError:
        return LLMPreflightResult(
            LLMPreflightCode.UNREACHABLE_GATEWAY,
            "The LLM gateway timed out during the bounded preflight probe.",
            model=config.model,
            endpoint=_safe_endpoint(config.endpoint),
        )
    except LLMResponseError as exc:
        return _classify_response_error(exc, config)
    except LLMGatewayError as exc:
        return LLMPreflightResult(
            LLMPreflightCode.PROBE_FAILED,
            f"The LLM gateway probe failed ({type(exc).__name__}).",
            model=config.model,
            endpoint=_safe_endpoint(config.endpoint),
        )
    except Exception as exc:  # noqa: BLE001, BROAD_EXCEPT_OK
        return LLMPreflightResult(
            LLMPreflightCode.PROBE_FAILED,
            f"Unexpected {type(exc).__name__} during the bounded LLM probe.",
            model=config.model,
            endpoint=_safe_endpoint(config.endpoint),
        )

    return LLMPreflightResult(
        LLMPreflightCode.READY,
        f"Verified structured route for model '{config.model}'.",
        model=config.model,
        endpoint=_safe_endpoint(config.endpoint),
        route=route,
    )


def _classify_response_error(exc: LLMResponseError, config) -> LLMPreflightResult:
    """Map an HTTP-shaped gateway error to a typed preflight code by status."""
    text = str(exc)
    status = exc.status_code or _status_code_from_error(text)
    if status == 503:
        code = LLMPreflightCode.UNREACHABLE_GATEWAY
    elif status in {401, 403}:
        code = LLMPreflightCode.AUTH_FAILED
    elif status == 404 or exc.error_type == "model_not_found":
        code = LLMPreflightCode.MODEL_NOT_FOUND
    elif status == 400 and (
        exc.error_kind == "structured_output_unsupported" or _schema_unsupported(text)
    ):
        code = LLMPreflightCode.UNSUPPORTED_STRUCTURED_OUTPUT
    elif status is not None and status >= 500:
        code = LLMPreflightCode.UNREACHABLE_GATEWAY
    else:
        code = LLMPreflightCode.PROBE_FAILED
    return LLMPreflightResult(
        code,
        f"The LLM gateway returned HTTP {status or 'unknown'} during preflight.",
        model=config.model,
        endpoint=_safe_endpoint(config.endpoint),
        error_type=exc.error_type,
        retry_after_seconds=exc.retry_after_seconds,
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


def _safe_endpoint(endpoint: str | None) -> str | None:
    if not endpoint:
        return None
    parsed = urlsplit(endpoint)
    if not parsed.scheme or not parsed.hostname:
        return None
    try:
        parsed_port = parsed.port
    except ValueError:
        return None
    port = f":{parsed_port}" if parsed_port is not None else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def _default_probe(config, api_key: str) -> GatewayProbe:
    """Build the real bounded structured probe from environment configuration."""

    def probe() -> dict | None:
        from vnalpha.assistant.gateway import LLMGatewayClient

        client = LLMGatewayClient(config, api_key=api_key)
        content, usage = client.chat(
            _PROBE_MESSAGES,
            response_schema=_PROBE_SCHEMA,
            stage="preflight",
        )
        structured_mode = usage.get("structured_output_mode")
        downgraded = usage.get("structured_output_downgraded")
        if structured_mode != "json_schema" or downgraded is not False:
            raise LLMResponseError(
                "LLM HTTP 400: json_schema unsupported",
                status_code=400,
                error_kind="structured_output_unsupported",
            )
        try:
            payload = json.loads(content)
        except (TypeError, json.JSONDecodeError) as exc:
            raise LLMGatewayError(
                "The structured preflight response was not valid JSON."
            ) from exc
        if payload != {"ok": True}:
            raise LLMGatewayError(
                "The structured preflight response failed schema verification."
            )
        route = usage.get("model_route") if isinstance(usage, dict) else None
        return route if isinstance(route, dict) else None

    return probe


__all__ = [
    "LLMPreflightCode",
    "LLMPreflightResult",
    "run_llm_preflight",
]
