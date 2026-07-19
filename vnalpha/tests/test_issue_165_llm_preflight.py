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
    "VNALPHA_LLM_TIMEOUT",
    "VNALPHA_LLM_MAX_OUTPUT_TOKENS",
    "VNALPHA_LLM_MAX_RETRIES",
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


def test_malformed_numeric_config_is_typed_before_any_probe(monkeypatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setenv("VNALPHA_LLM_TIMEOUT", "not-an-integer")

    def _probe():
        raise AssertionError("probe must not run with malformed configuration")

    result = run_llm_preflight(probe=_probe)

    assert result.code is LLMPreflightCode.MISSING_CONFIG
    assert "VNALPHA_LLM_TIMEOUT" in result.detail


def test_malformed_endpoint_port_is_typed_before_auth(monkeypatch) -> None:
    _configure(monkeypatch, api_key=False)
    monkeypatch.setenv("VNALPHA_LLM_ENDPOINT", "http://gateway.test:not-a-port")

    result = run_llm_preflight(probe=lambda: None)

    assert result.code is LLMPreflightCode.MISSING_CONFIG
    assert "VNALPHA_LLM_ENDPOINT" in result.detail


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://gateway.example.test/v1/chat/completions",
        "https://user:password@gateway.example.test/v1/chat/completions",
    ],
)
def test_credential_transport_rejects_insecure_or_userinfo_endpoint(
    monkeypatch, endpoint
) -> None:
    _configure(monkeypatch)
    monkeypatch.setenv("VNALPHA_LLM_ENDPOINT", endpoint)

    result = run_llm_preflight(probe=lambda: None)

    assert result.code is LLMPreflightCode.MISSING_CONFIG


def test_loopback_http_endpoint_remains_available(monkeypatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setenv(
        "VNALPHA_LLM_ENDPOINT", "http://127.0.0.1:7071/v1/chat/completions"
    )

    result = run_llm_preflight(
        probe=lambda: {"model_id": "verified-model", "profile": "default"}
    )

    assert result.code is LLMPreflightCode.READY


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


def test_explicit_key_is_passed_to_default_client_without_env_mutation(
    monkeypatch,
) -> None:
    from vnalpha.assistant import gateway

    _configure(monkeypatch)
    monkeypatch.setenv("VNALPHA_LLM_API_KEY", "environment-key")
    observed: dict[str, object] = {}

    class _Client:
        def __init__(self, config, **kwargs) -> None:
            observed["config"] = config
            observed.update(kwargs)

        def chat(self, messages, response_schema=None, **kwargs):
            return '{"ok": true}', {
                "model_route": {"model_id": "verified-model"},
                "structured_output_mode": "json_schema",
                "structured_output_downgraded": False,
            }

    monkeypatch.setattr(gateway, "LLMGatewayClient", _Client)

    result = run_llm_preflight(api_key="explicit-key")

    assert result.code is LLMPreflightCode.READY
    assert observed["api_key"] == "explicit-key"
    assert gateway.os.environ["VNALPHA_LLM_API_KEY"] == "environment-key"


@pytest.mark.parametrize(
    ("content", "mode", "downgraded", "expected"),
    [
        ("not-json", "json_schema", False, LLMPreflightCode.PROBE_FAILED),
        ('{"ok": false}', "json_schema", False, LLMPreflightCode.PROBE_FAILED),
        (
            '{"ok": true}',
            "json_object",
            True,
            LLMPreflightCode.UNSUPPORTED_STRUCTURED_OUTPUT,
        ),
    ],
)
def test_default_probe_requires_verified_strict_schema_response(
    monkeypatch, content, mode, downgraded, expected
) -> None:
    from vnalpha.assistant import gateway

    _configure(monkeypatch)

    class _Client:
        def __init__(self, config, **kwargs) -> None:
            pass

        def chat(self, messages, response_schema=None, **kwargs):
            return content, {
                "model_route": {"model_id": "verified-model"},
                "structured_output_mode": mode,
                "structured_output_downgraded": downgraded,
            }

    monkeypatch.setattr(gateway, "LLMGatewayClient", _Client)

    assert run_llm_preflight().code is expected


def test_llm_error_log_contains_metadata_only(monkeypatch) -> None:
    from vnalpha.assistant import gateway

    captured: dict[str, object] = {}

    class _Logger:
        def error(self, event: str, **fields) -> None:
            captured["event"] = event
            captured.update(fields)

    monkeypatch.setattr("structlog.get_logger", lambda _name: _Logger())

    gateway._log_llm_error(
        "preflight",
        LLMResponseError("LLM HTTP 401: Authorization: Bearer synthetic-sentinel"),
        cause=RuntimeError("private cause body"),
    )

    assert captured["error_type"] == "LLMResponseError"
    assert captured["cause_type"] == "RuntimeError"
    assert "synthetic-sentinel" not in repr(captured)
    assert "private cause body" not in repr(captured)


def test_unreachable_gateway_is_typed(monkeypatch) -> None:
    _configure(monkeypatch)

    def _probe():
        raise LLMTimeoutError("Model 'verified-model' failed after 3 attempt(s).")

    result = run_llm_preflight(probe=_probe)

    assert result.code is LLMPreflightCode.UNREACHABLE_GATEWAY


def test_unreachable_503_is_typed_and_preserves_gateway_error_info(monkeypatch) -> None:
    _configure(monkeypatch)

    def _probe():
        raise LLMResponseError(
            "LLM HTTP 503: temporary error",
            status_code=503,
            error_type="model_unavailable",
            retry_after_seconds=45,
        )

    result = run_llm_preflight(probe=_probe)

    assert result.code is LLMPreflightCode.UNREACHABLE_GATEWAY
    assert result.error_type == "model_unavailable"
    assert result.retry_after_seconds == 45
    assert result.remediation is not None
    assert "/health/umbrella" in result.remediation


def test_auth_failure_is_typed_from_http_401(monkeypatch) -> None:
    _configure(monkeypatch)

    def _probe():
        raise LLMResponseError("LLM HTTP 401: unauthorized")

    result = run_llm_preflight(probe=_probe)

    assert result.code is LLMPreflightCode.AUTH_FAILED


def test_response_error_detail_does_not_expose_raw_gateway_body(monkeypatch) -> None:
    _configure(monkeypatch)

    def _probe():
        raise LLMResponseError(
            "LLM HTTP 401: Authorization: Bearer raw-response-secret"
        )

    result = run_llm_preflight(probe=_probe)

    assert result.code is LLMPreflightCode.AUTH_FAILED
    assert "raw-response-secret" not in result.detail
    assert "Authorization" not in result.detail


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


def test_unexpected_probe_exception_is_sanitized(monkeypatch) -> None:
    _configure(monkeypatch)

    def _probe():
        raise RuntimeError("Authorization: Bearer super-secret-key")

    result = run_llm_preflight(probe=_probe)

    assert result.code is LLMPreflightCode.PROBE_FAILED
    assert "RuntimeError" in result.detail
    assert "super-secret-key" not in result.detail
    assert "Authorization" not in result.detail


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
        "error_type",
        "retry_after_seconds",
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


@pytest.mark.parametrize("json_flag", [False, True])
def test_preflight_cli_redacts_dynamic_model(monkeypatch, json_flag: bool) -> None:
    from typer.testing import CliRunner

    from vnalpha.cli import app

    private_fragment = "PREFLIGHT_MODEL_SECRET_28"
    control = "\x1b]8;;https://example.invalid\x1b\\model\x1b]8;;\x1b\\"
    hostile_model = f"verified password={private_fragment} {control}"
    monkeypatch.setenv(
        "VNALPHA_LLM_ENDPOINT", "https://gateway.example.test/v1/chat/completions"
    )
    monkeypatch.setenv("VNALPHA_MODEL_DEFAULT", hostile_model)
    monkeypatch.setenv("VNALPHA_LLM_MODEL", hostile_model)
    monkeypatch.setenv("VNALPHA_LLM_API_KEY", "")

    args = ["preflight", "--json"] if json_flag else ["preflight"]
    result = CliRunner().invoke(app, args)

    assert result.exit_code == 1
    assert private_fragment not in result.stdout
    assert "\x1b]8;" not in result.stdout
    assert "[REDACTED]" in result.stdout


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
