"""Tests for vnstock local data service.

Tests cover:
- Forbidden endpoint gate (no login/account/order endpoints)
- Allowed endpoint responses (healthz, providers, auth/status, etc.)
- Data-read only boundaries
- Service starts on a free port and responds correctly
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from unittest.mock import MagicMock

import pytest

from vnstock.service.server import _is_forbidden, run_server

# ---------------------------------------------------------------------------
# Unit tests for _is_forbidden helper
# ---------------------------------------------------------------------------


class TestIsForbidden:
    """Test the _is_forbidden path gate."""

    def test_auth_login_forbidden(self):
        assert _is_forbidden("/v1/auth/login") is True

    def test_auth_login_with_slash_forbidden(self):
        assert _is_forbidden("/v1/auth/login/") is True

    def test_order_forbidden(self):
        assert _is_forbidden("/v1/order") is True

    def test_order_subpath_forbidden(self):
        assert _is_forbidden("/v1/order/submit") is True

    def test_account_forbidden(self):
        assert _is_forbidden("/v1/account") is True

    def test_account_subpath_forbidden(self):
        assert _is_forbidden("/v1/account/info") is True

    def test_portfolio_forbidden(self):
        assert _is_forbidden("/v1/portfolio") is True

    def test_portfolio_subpath_forbidden(self):
        assert _is_forbidden("/v1/portfolio/holdings") is True

    def test_transfer_forbidden(self):
        assert _is_forbidden("/v1/transfer") is True

    def test_margin_forbidden(self):
        assert _is_forbidden("/v1/margin") is True

    def test_case_insensitive_forbidden(self):
        assert _is_forbidden("/V1/AUTH/LOGIN") is True
        assert _is_forbidden("/V1/Order") is True

    # --- allowed endpoints should NOT be forbidden ---

    def test_healthz_allowed(self):
        assert _is_forbidden("/healthz") is False

    def test_providers_allowed(self):
        assert _is_forbidden("/v1/providers") is False

    def test_auth_status_allowed(self):
        assert _is_forbidden("/v1/auth/status") is False

    def test_auth_providers_allowed(self):
        assert _is_forbidden("/v1/auth/providers") is False

    def test_market_allowed(self):
        assert _is_forbidden("/v1/market/ohlcv") is False

    def test_reference_allowed(self):
        assert _is_forbidden("/v1/reference/listing") is False

    def test_fundamental_allowed(self):
        assert _is_forbidden("/v1/fundamental/balance_sheet") is False

    def test_fund_allowed(self):
        assert _is_forbidden("/v1/fund/nav") is False


# ---------------------------------------------------------------------------
# Integration tests using a live test server on a free port
# ---------------------------------------------------------------------------


def _get_free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _fetch(url: str, timeout: float = 3.0) -> tuple[int, dict]:
    """Return (status_code, parsed_json) for a GET request."""
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read()
        return e.code, json.loads(body)


@pytest.fixture(scope="module")
def service_url():
    """Start a test server and return its base URL."""
    port = _get_free_port()
    stop = threading.Event()
    run_server("127.0.0.1", port, auth_manager=None, _stop_event=stop)
    time.sleep(0.1)  # Let the thread spin up
    url = f"http://127.0.0.1:{port}"
    yield url
    stop.set()


class TestHealthEndpoint:
    def test_healthz_returns_200(self, service_url):
        status, body = _fetch(f"{service_url}/healthz")
        assert status == 200

    def test_healthz_status_ok(self, service_url):
        _, body = _fetch(f"{service_url}/healthz")
        assert body["status"] == "ok"

    def test_healthz_service_name(self, service_url):
        _, body = _fetch(f"{service_url}/healthz")
        assert body["service"] == "vnstock"

    def test_health_alias(self, service_url):
        status, _ = _fetch(f"{service_url}/health")
        assert status == 200


class TestProvidersEndpoints:
    def test_providers_returns_200(self, service_url):
        status, body = _fetch(f"{service_url}/v1/providers")
        assert status == 200
        assert "providers" in body

    def test_providers_health_returns_200(self, service_url):
        status, body = _fetch(f"{service_url}/v1/providers/health")
        assert status == 200
        assert "health" in body
        assert "providers" in body
        assert isinstance(body["providers"], list)

    def test_providers_capabilities_returns_200(self, service_url):
        status, body = _fetch(f"{service_url}/v1/providers/capabilities")
        assert status == 200
        assert "capabilities" in body


class TestAuthEndpoints:
    def test_auth_status_no_manager(self, service_url):
        status, body = _fetch(f"{service_url}/v1/auth/status")
        assert status == 200
        assert "auth_status" in body

    def test_auth_status_no_token_material(self, service_url):
        """Auth status must never include token/credential material."""
        _, body = _fetch(f"{service_url}/v1/auth/status")
        body_str = json.dumps(body).lower()
        # No token/password/secret fields
        for dangerous in ["token", "password", "secret", "bearer", "credential"]:
            assert dangerous not in body_str, f"Found sensitive field: {dangerous}"

    def test_auth_providers_returns_200(self, service_url):
        status, body = _fetch(f"{service_url}/v1/auth/providers")
        assert status == 200


class TestForbiddenEndpoints:
    """All forbidden endpoints must return 404 (as if they don't exist)."""

    FORBIDDEN_PATHS = [
        "/v1/auth/login",
        "/v1/order",
        "/v1/order/submit",
        "/v1/account",
        "/v1/account/info",
        "/v1/portfolio",
        "/v1/portfolio/holdings",
        "/v1/transfer",
        "/v1/margin",
    ]

    @pytest.mark.parametrize("path", FORBIDDEN_PATHS)
    def test_forbidden_returns_404(self, service_url, path):
        status, body = _fetch(f"{service_url}{path}")
        assert status == 404, f"Expected 404 for {path}, got {status}"

    @pytest.mark.parametrize("path", FORBIDDEN_PATHS)
    def test_forbidden_returns_not_found_error(self, service_url, path):
        _, body = _fetch(f"{service_url}{path}")
        assert body.get("error") == "not_found", (
            f"Expected 'not_found' error for {path}"
        )


class TestUnknownEndpoints:
    def test_unknown_returns_404(self, service_url):
        status, _ = _fetch(f"{service_url}/v1/unknown")
        assert status == 404

    def test_root_returns_404(self, service_url):
        status, _ = _fetch(f"{service_url}/")
        assert status == 404


class TestDataReadOnlyBoundary:
    """Verify the service is data-read only - no write/mutating endpoints."""

    def test_no_login_endpoint(self, service_url):
        """There must be no /v1/auth/login endpoint."""
        status, _ = _fetch(f"{service_url}/v1/auth/login")
        assert status == 404

    def test_no_order_endpoint(self, service_url):
        status, _ = _fetch(f"{service_url}/v1/order")
        assert status == 404

    def test_no_portfolio_endpoint(self, service_url):
        status, _ = _fetch(f"{service_url}/v1/portfolio")
        assert status == 404

    def test_no_account_endpoint(self, service_url):
        status, _ = _fetch(f"{service_url}/v1/account")
        assert status == 404


class TestAuthManagerIntegration:
    """Test server behavior when auth_manager is provided."""

    def test_auth_status_with_manager(self):
        """Auth status endpoint returns safe data from auth manager."""
        port = _get_free_port()
        stop = threading.Event()

        mock_manager = MagicMock()
        mock_manager.auth_status_all.return_value = {
            "tcbs": {
                "authenticated": True,
                "provider": "tcbs",
                "source": "local_file",
                "_token": "secret-token-should-not-appear",
            }
        }

        run_server("127.0.0.1", port, auth_manager=mock_manager, _stop_event=stop)
        time.sleep(0.1)

        status, body = _fetch(f"http://127.0.0.1:{port}/v1/auth/status")
        stop.set()

        assert status == 200
        assert "auth_status" in body
        auth_status = body["auth_status"]

        # Should have tcbs info but NO token material
        if "tcbs" in auth_status:
            body_str = json.dumps(auth_status)
            assert "secret-token" not in body_str
            assert "_token" not in body_str
