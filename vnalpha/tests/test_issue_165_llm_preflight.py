"""Focused tests for the issue #165 assistant LLM startup preflight.

The preflight must distinguish missing configuration, an unreachable gateway,
an authentication failure, a missing model and unsupported structured output,
verify one real route through a fake gateway (no live network), and never leak
secrets or prompt content.
"""

from __future__ import annotations

import pytest

from vnalpha.assistant.errors import (
    LLMConfigError,
    LLMGatewayError,
    LLMNoCompatibleFallbackError,
    LLMResponseError,
    LLMTimeoutError,
)
from vnalpha.assistant.preflight import (
    LLMPreflightCode,
    run_llm_preflight,
)

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


def _configure(monkeypatch, *, api_key: bool = True) -> None:
    for name in _LLM_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(
        "VNALPHA_LLM_ENDPOINT", "https://gateway.example.test/v1/chat/completions"
    )
    monkeypatch.setenv("VNALPHA_LLM_MODEL", "verified-model")
    if api_key:
        monkeypatch.setenv("VNALPHA_LLM_API_KEY", "unit-test-key")


def test_missing_config_is_typed_before_any_probe(monkeypatch) -> None:
    for name in _LLM_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VNALPHA_LLM_MODEL", "verified-model")

    def _probe():
        raise AssertionError("probe must not run without configuration")

    result = run_llm_preflight(probe=_probe)

    assert result.code is LLMPreflightCode.MISSING_CONFIG
    assert not result.ready
    assert result.remediation


def test_missing_api_key_reports_auth_not_configured(monkeypatch) -> None:
    _configure(monkeypatch, api_key=False)

    def _probe():
        raise AssertionError("probe must not run without an API key")

    result = run_llm_preflight(probe=_probe, api_key="")

    assert result.code is LLMPreflightCode.AUTH_NOT_CONFIGURED
    assert result.model == "verified-model"


def test_ready_records_route_identity(monkeypatch) -> None:
    _configure(monkeypatch)
    route = {"model_id": "verified-model", "profile": "default"}

    result = run_llm_preflight(probe=lambda: route)

    assert result.code is LLMPreflightCode.READY
    assert result.ready
    assert result.route == route
    assert result.model == "verified-model"


def test_unreachable_gateway_is_typed(monkeypatch) -> None:
    _configure(monkeypatch)

    def _probe():
        raise LLMTimeoutError("Model 'verified-model' failed after 3 attempt(s).")

    result = run_llm_preflight(probe=_probe)

    assert result.code is LLMPreflightCode.UNREACHABLE_GATEWAY


def test_auth_failure_is_typed_from_http_401(monkeypatch) -> None:
    _configure(monkeypatch)

    def _probe():
        raise LLMResponseError("LLM HTTP 401: unauthorized")

    result = run_llm_preflight(probe=_probe)

    assert result.code is LLMPreflightCode.AUTH_FAILED


def test_missing_model_is_typed_from_http_404(monkeypatch) -> None:
    _configure(monkeypatch)

    def _probe():
        raise LLMResponseError("LLM HTTP 404: model not found")

    result = run_llm_preflight(probe=_probe)

    assert result.code is LLMPreflightCode.MODEL_NOT_FOUND


def test_invalid_routing_config_reports_missing_model(monkeypatch) -> None:
    _configure(monkeypatch)

    def _probe():
        raise LLMConfigError("Invalid model routing configuration: no model")

    result = run_llm_preflight(probe=_probe)

    assert result.code is LLMPreflightCode.MISSING_MODEL


def test_unsupported_structured_output_is_typed(monkeypatch) -> None:
    _configure(monkeypatch)

    def _probe():
        raise LLMNoCompatibleFallbackError(
            stage="preflight",
            primary_model="verified-model",
            required_capability="json_schema",
            primary_error=LLMResponseError("LLM HTTP 400: json_schema unsupported"),
        )

    result = run_llm_preflight(probe=_probe)

    assert result.code is LLMPreflightCode.UNSUPPORTED_STRUCTURED_OUTPUT


def test_no_fallback_wrapping_transport_error_reports_unreachable(monkeypatch) -> None:
    # A single-model route whose primary failure was a real transport timeout
    # must be reported as unreachable, not masked as a structured-output gap.
    _configure(monkeypatch)

    def _probe():
        raise LLMNoCompatibleFallbackError(
            stage="preflight",
            primary_model="verified-model",
            required_capability="json_schema",
            primary_error=LLMTimeoutError("Model failed after 3 attempt(s)."),
        )

    result = run_llm_preflight(probe=_probe)

    assert result.code is LLMPreflightCode.UNREACHABLE_GATEWAY


def test_generic_gateway_error_is_probe_failed(monkeypatch) -> None:
    _configure(monkeypatch)

    def _probe():
        raise LLMGatewayError("all configured model routes failed")

    result = run_llm_preflight(probe=_probe)

    assert result.code is LLMPreflightCode.PROBE_FAILED


def test_status_dict_is_redaction_safe(monkeypatch) -> None:
    _configure(monkeypatch)
    result = run_llm_preflight(
        probe=lambda: {"model_id": "verified-model", "profile": "default"}
    )

    status = result.to_status_dict()

    # No API key or prompt content is ever surfaced.
    serialized = repr(status)
    assert "unit-test-key" not in serialized
    assert "Reply with" not in serialized
    assert set(status) == {
        "ready",
        "code",
        "detail",
        "model",
        "endpoint",
        "route",
        "remediation",
    }


@pytest.mark.parametrize(
    "code",
    [
        LLMPreflightCode.MISSING_CONFIG,
        LLMPreflightCode.AUTH_NOT_CONFIGURED,
        LLMPreflightCode.MISSING_MODEL,
        LLMPreflightCode.UNREACHABLE_GATEWAY,
        LLMPreflightCode.AUTH_FAILED,
        LLMPreflightCode.MODEL_NOT_FOUND,
        LLMPreflightCode.UNSUPPORTED_STRUCTURED_OUTPUT,
    ],
)
def test_every_failure_code_has_remediation(code) -> None:
    from vnalpha.assistant.preflight import LLMPreflightResult

    result = LLMPreflightResult(code, "detail")
    assert result.remediation


def test_preflight_cli_exits_nonzero_when_unavailable(monkeypatch) -> None:
    from typer.testing import CliRunner

    from vnalpha.cli import app

    # Missing API key deterministically yields AUTH_NOT_CONFIGURED before any
    # probe. Set explicit config (dotenv uses override=False, so these win) and
    # force the key empty so the CLI cannot reach the network.
    monkeypatch.setenv(
        "VNALPHA_LLM_ENDPOINT", "https://gateway.example.test/v1/chat/completions"
    )
    monkeypatch.setenv("VNALPHA_MODEL_DEFAULT", "verified-model")
    monkeypatch.setenv("VNALPHA_LLM_MODEL", "verified-model")
    monkeypatch.setenv("VNALPHA_LLM_API_KEY", "")

    result = CliRunner().invoke(app, ["preflight"])

    assert result.exit_code == 1
    assert "UNAVAILABLE" in result.stdout
    assert "slash commands remain usable" in result.stdout


def test_preflight_cli_json_is_secret_free(monkeypatch) -> None:
    from typer.testing import CliRunner

    from vnalpha.cli import app

    monkeypatch.setenv(
        "VNALPHA_LLM_ENDPOINT", "https://gateway.example.test/v1/chat/completions"
    )
    monkeypatch.setenv("VNALPHA_MODEL_DEFAULT", "verified-model")
    monkeypatch.setenv("VNALPHA_LLM_MODEL", "verified-model")
    monkeypatch.setenv("VNALPHA_LLM_API_KEY", "super-secret-key")
    # Empty key path is not taken here; instead assert no secret leaks in output
    # for a route that fails fast without a live provider. Point at an
    # unroutable endpoint so the probe fails typed rather than hanging.
    monkeypatch.setenv("VNALPHA_LLM_ENDPOINT", "http://127.0.0.1:1/v1/chat/completions")
    monkeypatch.setenv("VNALPHA_LLM_TIMEOUT", "1")
    monkeypatch.setenv("VNALPHA_LLM_MAX_RETRIES", "0")

    result = CliRunner().invoke(app, ["preflight", "--json"])

    assert result.exit_code == 1
    assert '"ready": false' in result.stdout
    assert "super-secret-key" not in result.stdout
