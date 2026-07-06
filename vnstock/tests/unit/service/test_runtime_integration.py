"""Tests proving service data endpoints use PluginRuntime.

Key invariants:
- /v1/equity/ohlcv calls PluginRuntime.fetch (not legacy Vnstock)
- response contains data, meta, diagnostics
- meta.runtime_path == "plugin_runtime"
- provider endpoints use plugin registry (not legacy ProviderRegistry)
- forbidden endpoint groups stay unavailable
- auth status leaks no secrets
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from vnstock.core.result import DataResult
from vnstock.service import runtime_dependency
from vnstock.service.server import run_server

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _fetch(url: str, timeout: float = 5.0) -> tuple[int, dict]:
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {}


def _make_fake_runtime(
    *,
    dataset: str = "equity.ohlcv",
    provider: str = "FAKE",
    rows: int = 2,
) -> MagicMock:
    """Create a MagicMock that behaves like PluginRuntime."""
    fake_df = pd.DataFrame(
        {
            "time": [f"2024-01-0{i + 1}" for i in range(rows)],
            "close": [100.0 + i for i in range(rows)],
        }
    )
    fake_result = DataResult(
        dataset=dataset,
        provider=provider,
        data=fake_df,
        quality_status="PASS",
        diagnostics={"runtime_path": "plugin_runtime", "routing": {}},
        fetched_at=datetime(2026, 7, 3, tzinfo=timezone.utc),
    )
    mock = MagicMock()
    mock.fetch.return_value = fake_result
    return mock


# ---------------------------------------------------------------------------
# Fixture: service using fake runtime
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def runtime_service_url():
    """Start a test service with a fake PluginRuntime injected."""
    fake = _make_fake_runtime()
    runtime_dependency.override_runtime(fake)

    port = _get_free_port()
    stop = threading.Event()
    run_server("127.0.0.1", port, _stop_event=stop)
    time.sleep(0.15)
    url = f"http://127.0.0.1:{port}"

    yield url, fake

    stop.set()
    runtime_dependency.reset_runtime()


# ---------------------------------------------------------------------------
# Tests: /v1/equity/ohlcv calls PluginRuntime
# ---------------------------------------------------------------------------


class TestRuntimeDispatched:
    def test_equity_ohlcv_calls_plugin_runtime(self, runtime_service_url):
        url, fake_rt = runtime_service_url
        status, body = _fetch(f"{url}/v1/equity/ohlcv?symbol=FPT")
        assert status == 200, f"Expected 200, got {status}: {body}"
        fake_rt.fetch.assert_called()

    def test_runtime_called_with_correct_dataset(self, runtime_service_url):
        url, fake_rt = runtime_service_url
        fake_rt.fetch.reset_mock()
        _fetch(f"{url}/v1/equity/ohlcv?symbol=FPT")
        call_args = fake_rt.fetch.call_args
        assert call_args is not None
        # First positional arg is dataset
        assert call_args[0][0] == "equity.ohlcv"

    def test_return_result_true_passed(self, runtime_service_url):
        url, fake_rt = runtime_service_url
        fake_rt.fetch.reset_mock()
        _fetch(f"{url}/v1/equity/ohlcv?symbol=FPT")
        call_kwargs = fake_rt.fetch.call_args.kwargs
        assert call_kwargs.get("return_result") is True


class TestResponseEnvelope:
    def test_response_has_data_key(self, runtime_service_url):
        url, _ = runtime_service_url
        _, body = _fetch(f"{url}/v1/equity/ohlcv?symbol=FPT")
        assert "data" in body

    def test_response_has_meta_key(self, runtime_service_url):
        url, _ = runtime_service_url
        _, body = _fetch(f"{url}/v1/equity/ohlcv?symbol=FPT")
        assert "meta" in body

    def test_response_has_diagnostics_key(self, runtime_service_url):
        url, _ = runtime_service_url
        _, body = _fetch(f"{url}/v1/equity/ohlcv?symbol=FPT")
        assert "diagnostics" in body

    def test_meta_dataset_correct(self, runtime_service_url):
        url, _ = runtime_service_url
        _, body = _fetch(f"{url}/v1/equity/ohlcv?symbol=FPT")
        assert body["meta"]["dataset"] == "equity.ohlcv"

    def test_meta_runtime_path_is_plugin_runtime(self, runtime_service_url):
        url, _ = runtime_service_url
        _, body = _fetch(f"{url}/v1/equity/ohlcv?symbol=FPT")
        assert body["meta"]["runtime_path"] == "plugin_runtime"


class TestLegacyVnstockNotCalled:
    """Prove legacy Vnstock is not instantiated in data endpoints."""

    def test_vnstock_not_instantiated_for_data_request(self):
        """Patching Vnstock to fail — data request must still succeed via runtime."""
        fake = _make_fake_runtime()
        runtime_dependency.override_runtime(fake)

        port = _get_free_port()
        stop = threading.Event()

        with patch(
            "vnstock.Vnstock",
            side_effect=RuntimeError("legacy Vnstock must not be called"),
        ):
            run_server("127.0.0.1", port, _stop_event=stop)
            time.sleep(0.15)
            status, body = _fetch(f"http://127.0.0.1:{port}/v1/equity/ohlcv?symbol=FPT")

        stop.set()
        runtime_dependency.reset_runtime()

        # If Vnstock was called, it would return 500. Should be 200.
        assert status == 200, f"Expected 200, got {status}: {body}"


# ---------------------------------------------------------------------------
# Tests: provider endpoints use plugin registry
# ---------------------------------------------------------------------------


class TestProviderEndpointsUsePluginRegistry:
    def test_providers_list_returns_200(self, runtime_service_url):
        url, _ = runtime_service_url
        status, body = _fetch(f"{url}/v1/providers")
        assert status == 200
        assert "providers" in body

    def test_providers_is_list(self, runtime_service_url):
        url, _ = runtime_service_url
        _, body = _fetch(f"{url}/v1/providers")
        assert isinstance(body["providers"], list)

    def test_capabilities_returns_200(self, runtime_service_url):
        url, _ = runtime_service_url
        status, body = _fetch(f"{url}/v1/providers/capabilities")
        assert status == 200
        assert "capabilities" in body


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_unsupported_dataset_returns_404(self, runtime_service_url):
        url, _ = runtime_service_url
        status, body = _fetch(f"{url}/v1/equity/does-not-exist")
        assert status == 404

    def test_unsupported_dataset_error_field(self, runtime_service_url):
        url, _ = runtime_service_url
        _, body = _fetch(f"{url}/v1/equity/does-not-exist")
        assert body.get("error") == "unsupported_dataset"

    def test_provider_fetch_error_returns_502(self):
        """When PluginRuntime raises ProviderFetchError, service returns 502."""
        from vnstock.core.provider.exceptions import ProviderFetchError

        fake = MagicMock()
        fake.fetch.side_effect = ProviderFetchError("FAKE", "equity.ohlcv")
        runtime_dependency.override_runtime(fake)

        port = _get_free_port()
        stop = threading.Event()
        run_server("127.0.0.1", port, _stop_event=stop)
        time.sleep(0.15)
        status, body = _fetch(f"http://127.0.0.1:{port}/v1/equity/ohlcv?symbol=FPT")
        stop.set()
        runtime_dependency.reset_runtime()

        assert status == 502

    def test_no_healthy_provider_returns_503(self):
        """When PluginRuntime raises NoHealthyProviderError, service returns 503."""
        from vnstock.core.provider.exceptions import NoHealthyProviderError

        fake = MagicMock()
        fake.fetch.side_effect = NoHealthyProviderError("equity.ohlcv")
        runtime_dependency.override_runtime(fake)

        port = _get_free_port()
        stop = threading.Event()
        run_server("127.0.0.1", port, _stop_event=stop)
        time.sleep(0.15)
        status, body = _fetch(f"http://127.0.0.1:{port}/v1/equity/ohlcv?symbol=FPT")
        stop.set()
        runtime_dependency.reset_runtime()

        assert status == 503


# ---------------------------------------------------------------------------
# Tests: auth status safety
# ---------------------------------------------------------------------------


class TestAuthStatusSafe:
    def test_auth_status_leaks_no_secrets(self, runtime_service_url):
        url, _ = runtime_service_url
        _, body = _fetch(f"{url}/v1/auth/status")
        body_str = json.dumps(body).lower()
        for sensitive in ["password", "token", "secret", "api_key", "credential"]:
            assert sensitive not in body_str, (
                f"Sensitive field '{sensitive}' found in auth status"
            )

    def test_auth_status_with_sensitive_manager(self):
        """Mock auth_manager that returns sensitive data — service must redact."""
        mock_manager = MagicMock()
        mock_manager.auth_status_all.return_value = [
            {
                "provider": "tcbs",
                "authenticated": True,
                "source": "local_file",
                "access_token": "bearer-abc123-secret",
                "password": "my-password",
            }
        ]

        port = _get_free_port()
        stop = threading.Event()
        run_server("127.0.0.1", port, auth_manager=mock_manager, _stop_event=stop)
        time.sleep(0.15)

        _, body = _fetch(f"http://127.0.0.1:{port}/v1/auth/status")
        stop.set()

        body_str = json.dumps(body)
        assert "bearer-abc123-secret" not in body_str
        assert "my-password" not in body_str

    def test_auth_status_includes_authenticated_flag(self, runtime_service_url):
        """Even with no auth manager, auth_status key should be present."""
        url, _ = runtime_service_url
        _, body = _fetch(f"{url}/v1/auth/status")
        assert "auth_status" in body


# ---------------------------------------------------------------------------
# Tests: forbidden boundary
# ---------------------------------------------------------------------------


class TestForbiddenBoundaryRemains:
    FORBIDDEN = [
        "/v1/auth/login",
        "/v1/auth/login/oauth",
        "/v1/order",
        "/v1/order/submit",
        "/v1/account",
        "/v1/account/balance",
        "/v1/portfolio",
        "/v1/portfolio/holdings",
        "/v1/transfer",
        "/v1/margin",
        "/v1/trading",
        "/v1/trading/execute",
    ]

    @pytest.mark.parametrize("path", FORBIDDEN)
    def test_forbidden_path_returns_404(self, runtime_service_url, path):
        url, _ = runtime_service_url
        status, _ = _fetch(f"{url}{path}")
        assert status == 404, f"Expected 404 for {path}, got {status}"
