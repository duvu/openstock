"""
Closure test suite for Phase 3.5 (PluginRuntime default execution path)
and Phase 4 (local data service runtime).

These tests prove:
- PluginRuntime.fetch returns DataResult when return_result=True
- Runtime validates params, records success/failure, attaches diagnostics
- DataFrame return path preserves metadata in attrs
- runtime_path is always attached to diagnostics
- Strict contract validation raises the expected error
- Service data endpoints call injected PluginRuntime
- Service response uses data/meta/diagnostics envelope
- Provider endpoints use plugin registry output
- Auth status endpoint works with/without auth manager
- Unavailable endpoint groups stay unavailable (404)
- CLI entrypoints exist in package metadata

No live provider calls. All tests use FakeProviderPlugin or MagicMock.
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

from tests.fixtures.fake_provider import FakeProviderPlugin
from vnstock.core.contracts.base import DatasetContract, DatasetContractRegistry
from vnstock.core.provider.exceptions import (
    DatasetContractError,
    ProviderFetchError,
)
from vnstock.core.provider.health import InMemoryProviderHealthStore
from vnstock.core.provider.plugin_registry import PluginRegistry
from vnstock.core.result import DataResult
from vnstock.core.runtime.plugin_runtime import PluginRuntime
from vnstock.service import runtime_dependency
from vnstock.service.server import run_server

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry(name: str = "FAKE") -> PluginRegistry:
    reg = PluginRegistry()
    reg.register(FakeProviderPlugin(name))
    return reg


def _make_runtime(provider_name: str = "FAKE") -> PluginRuntime:
    reg = _make_registry(provider_name)
    store = InMemoryProviderHealthStore()
    return PluginRuntime(registry=reg, health_store=store)


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


def _make_fake_runtime_mock(
    *,
    dataset: str = "equity.ohlcv",
    provider: str = "FAKE",
    rows: int = 2,
) -> MagicMock:
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
# Service fixture: shared per module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def closure_service_url():
    """Start a test service with a fake PluginRuntime injected."""
    fake = _make_fake_runtime_mock()
    runtime_dependency.override_runtime(fake)

    port = _get_free_port()
    stop = threading.Event()
    run_server("127.0.0.1", port, _stop_event=stop)
    time.sleep(0.15)
    url = f"http://127.0.0.1:{port}"

    yield url, fake

    stop.set()
    runtime_dependency.reset_runtime()


# ===========================================================================
# Phase 3.5: PluginRuntime default execution path
# ===========================================================================


class TestPluginRuntimeReturnResult:
    """Phase 3.5 – return_result=True returns DataResult."""

    def test_fetch_return_result_true_gives_data_result(self):
        rt = _make_runtime()
        result = rt.fetch("equity.ohlcv", {}, return_result=True)
        assert isinstance(result, DataResult)

    def test_data_result_has_provider(self):
        rt = _make_runtime()
        result = rt.fetch("equity.ohlcv", {}, return_result=True)
        assert isinstance(result, DataResult)
        assert result.provider == "FAKE"

    def test_data_result_has_dataset(self):
        rt = _make_runtime()
        result = rt.fetch("equity.ohlcv", {}, return_result=True)
        assert isinstance(result, DataResult)
        assert result.dataset == "equity.ohlcv"

    def test_data_result_data_is_dataframe(self):
        rt = _make_runtime()
        result = rt.fetch("equity.ohlcv", {}, return_result=True)
        assert isinstance(result, DataResult)
        assert isinstance(result.data, pd.DataFrame)

    def test_fetch_default_returns_dataframe(self):
        rt = _make_runtime()
        result = rt.fetch("equity.ohlcv", {})
        assert isinstance(result, pd.DataFrame)


class TestPluginRuntimeDiagnostics:
    """Phase 3.5 – Runtime attaches routing diagnostics and runtime_path."""

    def test_runtime_path_in_diagnostics(self):
        rt = _make_runtime()
        result = rt.fetch("equity.ohlcv", {}, return_result=True)
        assert isinstance(result, DataResult)
        assert result.diagnostics is not None
        assert result.diagnostics.get("runtime_path") == "plugin_runtime"

    def test_routing_diagnostics_attached(self):
        rt = _make_runtime()
        result = rt.fetch("equity.ohlcv", {}, return_result=True)
        assert isinstance(result, DataResult)
        assert "routing" in (result.diagnostics or {})

    def test_diagnostics_has_latency_ms(self):
        rt = _make_runtime()
        result = rt.fetch("equity.ohlcv", {}, return_result=True)
        assert isinstance(result, DataResult)
        assert "latency_ms" in (result.diagnostics or {})

    def test_custom_runtime_path_label(self):
        reg = _make_registry()
        rt = PluginRuntime(
            registry=reg,
            health_store=InMemoryProviderHealthStore(),
            runtime_path="custom_runtime",
        )
        result = rt.fetch("equity.ohlcv", {}, return_result=True)
        assert isinstance(result, DataResult)
        assert result.diagnostics is not None
        assert result.diagnostics.get("runtime_path") == "custom_runtime"


class TestPluginRuntimeDataFrameAttrs:
    """Phase 3.5 – DataFrame return path preserves metadata attrs."""

    def test_df_attrs_has_provider(self):
        rt = _make_runtime()
        df = rt.fetch("equity.ohlcv", {})
        assert df.attrs.get("provider") == "FAKE"

    def test_df_attrs_has_dataset(self):
        rt = _make_runtime()
        df = rt.fetch("equity.ohlcv", {})
        assert df.attrs.get("dataset") == "equity.ohlcv"

    def test_df_attrs_has_diagnostics(self):
        rt = _make_runtime()
        df = rt.fetch("equity.ohlcv", {})
        assert "diagnostics" in df.attrs

    def test_df_attrs_runtime_path_in_diagnostics(self):
        rt = _make_runtime()
        df = rt.fetch("equity.ohlcv", {})
        diag = df.attrs.get("diagnostics") or {}
        assert diag.get("runtime_path") == "plugin_runtime"


class TestPluginRuntimeHealthRecording:
    """Phase 3.5 – Runtime records success/failure on health store."""

    def test_success_recorded_after_fetch(self):
        from vnstock.core.provider.health import HealthStatus

        store = InMemoryProviderHealthStore()
        reg = _make_registry("FAKE")
        rt = PluginRuntime(registry=reg, health_store=store)
        rt.fetch("equity.ohlcv", {})
        h = store.get("FAKE", "equity.ohlcv")
        assert h.status == HealthStatus.HEALTHY

    def test_failure_recorded_after_fetch_error(self):
        class ErrorProvider:
            name = "ERRP"

            def capabilities(self) -> dict:
                return {
                    "equity.ohlcv": {
                        "supported": True,
                        "status": "stable",
                        "auth_required": False,
                        "intervals": [],
                    }
                }

            def fetch(self, dataset: str, params: dict) -> pd.DataFrame:
                raise ProviderFetchError("ERRP", "equity.ohlcv")

            def validate_params(self, dataset: str, params: dict) -> None:
                pass

            def diagnostics(self) -> dict:
                return {"name": "ERRP"}

            def auth_spec(self, dataset: str):
                from vnstock.core.auth.spec import AuthSpec

                return AuthSpec.no_auth()

        store = InMemoryProviderHealthStore()
        reg = PluginRegistry()
        reg.register(ErrorProvider())
        rt = PluginRuntime(registry=reg, health_store=store)
        with pytest.raises(ProviderFetchError):
            rt.fetch("equity.ohlcv", {})
        h = store.get("ERRP", "equity.ohlcv")
        assert h.failure_count >= 1


class TestPluginRuntimeContractValidation:
    """Phase 3.5 – Strict contract validation raises expected error."""

    def _runtime_with_contract(self) -> PluginRuntime:
        contract = DatasetContract(
            dataset="equity.ohlcv",
            required_columns=["time", "open", "high", "low", "close", "volume"],
        )
        contract_reg = DatasetContractRegistry()
        contract_reg.register(contract)
        reg = _make_registry("FAKE")
        return PluginRuntime(
            registry=reg,
            health_store=InMemoryProviderHealthStore(),
            contract_registry=contract_reg,
        )

    def test_strict_mode_raises_on_missing_columns(self):
        """FakeProviderPlugin returns a DataFrame missing required columns."""
        rt = self._runtime_with_contract()

        # FakeProviderPlugin.fetch for equity.ohlcv returns symbol/time/open/high/low/close/volume
        # so it should actually pass; use a fake that returns partial data
        class PartialProvider:
            name = "PARTIAL"

            def capabilities(self) -> dict:
                return {
                    "equity.ohlcv": {
                        "supported": True,
                        "status": "stable",
                        "auth_required": False,
                        "intervals": [],
                    }
                }

            def fetch(self, dataset: str, params: dict) -> pd.DataFrame:
                return pd.DataFrame({"time": ["2024-01-01"]})  # missing cols

            def validate_params(self, dataset: str, params: dict) -> None:
                pass

            def diagnostics(self) -> dict:
                return {"name": "PARTIAL"}

            def auth_spec(self, dataset: str):
                from vnstock.core.auth.spec import AuthSpec

                return AuthSpec.no_auth()

        contract = DatasetContract(
            dataset="equity.ohlcv",
            required_columns=["time", "open", "high", "low", "close", "volume"],
        )
        contract_reg = DatasetContractRegistry()
        contract_reg.register(contract)
        reg = PluginRegistry()
        reg.register(PartialProvider())
        rt = PluginRuntime(
            registry=reg,
            health_store=InMemoryProviderHealthStore(),
            contract_registry=contract_reg,
        )
        with pytest.raises(DatasetContractError):
            rt.fetch("equity.ohlcv", {}, validate=True, quality_mode="strict")


class TestPluginRuntimeParamsValidation:
    """Phase 3.5 – Runtime validates params before provider fetch."""

    def test_invalid_params_raise_platform_error(self):
        from vnstock.core.provider.exceptions import VnstockPlatformError

        class StrictProvider:
            name = "STRICT"

            def capabilities(self) -> dict:
                return {
                    "equity.ohlcv": {
                        "supported": True,
                        "status": "stable",
                        "auth_required": False,
                        "intervals": [],
                    }
                }

            def fetch(self, dataset: str, params: dict) -> pd.DataFrame:
                return pd.DataFrame()

            def validate_params(self, dataset: str, params: dict) -> None:
                if "symbol" not in params:
                    raise ValueError("symbol is required")

            def diagnostics(self) -> dict:
                return {"name": "STRICT"}

            def auth_spec(self, dataset: str):
                from vnstock.core.auth.spec import AuthSpec

                return AuthSpec.no_auth()

        reg = PluginRegistry()
        reg.register(StrictProvider())
        rt = PluginRuntime(registry=reg, health_store=InMemoryProviderHealthStore())
        with pytest.raises(VnstockPlatformError, match="Invalid parameters"):
            rt.fetch("equity.ohlcv", {})  # no symbol → should fail validation


# ===========================================================================
# Phase 4: Service runtime closure
# ===========================================================================


class TestServiceCallsPluginRuntime:
    """Phase 4 – /v1/equity/ohlcv calls injected PluginRuntime."""

    def test_equity_ohlcv_calls_runtime_fetch(self, closure_service_url):
        url, fake_rt = closure_service_url
        fake_rt.fetch.reset_mock()
        status, body = _fetch(f"{url}/v1/equity/ohlcv?symbol=VNM")
        assert status == 200, f"Expected 200, got {status}: {body}"
        fake_rt.fetch.assert_called()

    def test_runtime_called_with_equity_ohlcv_dataset(self, closure_service_url):
        url, fake_rt = closure_service_url
        fake_rt.fetch.reset_mock()
        _fetch(f"{url}/v1/equity/ohlcv?symbol=VNM")
        call_args = fake_rt.fetch.call_args
        assert call_args is not None
        assert call_args[0][0] == "equity.ohlcv"

    def test_return_result_true_passed_to_runtime(self, closure_service_url):
        url, fake_rt = closure_service_url
        fake_rt.fetch.reset_mock()
        _fetch(f"{url}/v1/equity/ohlcv?symbol=VNM")
        call_kwargs = fake_rt.fetch.call_args.kwargs
        assert call_kwargs.get("return_result") is True

    def test_fiinquantx_query_cannot_disable_strict_validation(
        self, closure_service_url
    ):
        url, fake_rt = closure_service_url
        fake_rt.fetch.reset_mock()

        status, _ = _fetch(
            f"{url}/v1/equity/ohlcv?symbol=VNM&source=FIINQUANTX"
            "&validate=false&quality_mode=warn"
        )

        assert status == 200
        call_kwargs = fake_rt.fetch.call_args.kwargs
        assert call_kwargs["validate"] is True
        assert call_kwargs["quality_mode"] == "strict"

    def test_invalid_fiinquantx_frame_returns_contract_error(self):
        class InvalidProvider(FakeProviderPlugin):
            def fetch(self, dataset, params):
                return pd.DataFrame(
                    {
                        "symbol": ["VNM"],
                        "time": ["not-a-timestamp"],
                        "open": [10.0],
                        "high": [8.0],
                        "low": [9.0],
                        "close": [11.0],
                        "volume": [-1.0],
                    }
                )

        registry = PluginRegistry()
        registry.register(InvalidProvider("FIINQUANTX"))
        runtime_dependency.override_runtime(PluginRuntime(registry=registry))
        port = _get_free_port()
        stop = threading.Event()
        run_server("127.0.0.1", port, _stop_event=stop)
        time.sleep(0.15)
        try:
            status, body = _fetch(
                f"http://127.0.0.1:{port}/v1/equity/ohlcv"
                "?symbol=VNM&source=FIINQUANTX&validate=false"
            )
        finally:
            stop.set()
            runtime_dependency.override_runtime(_make_fake_runtime_mock())

        assert status == 422
        assert body["error"] == "contract_validation_failed"
        assert body["retryable"] is False

    def test_valid_empty_fiinquantx_frame_returns_success(self):
        from vnstock.providers.fiinquantx.normalize import normalize_ohlcv

        class EmptyProvider(FakeProviderPlugin):
            def fetch(self, dataset, params):
                return normalize_ohlcv(pd.DataFrame(), dataset)

        registry = PluginRegistry()
        registry.register(EmptyProvider("FIINQUANTX"))
        runtime_dependency.override_runtime(PluginRuntime(registry=registry))
        port = _get_free_port()
        stop = threading.Event()
        run_server("127.0.0.1", port, _stop_event=stop)
        time.sleep(0.15)
        try:
            status, body = _fetch(
                f"http://127.0.0.1:{port}/v1/equity/ohlcv"
                "?symbol=VNM&source=FIINQUANTX&validate=false"
            )
        finally:
            stop.set()
            runtime_dependency.override_runtime(_make_fake_runtime_mock())

        assert status == 200
        assert body["data"] == []
        assert body["meta"]["quality_status"] == "PASS"

    def test_legacy_vnstock_not_called_for_data_endpoints(self, closure_service_url):
        """Data endpoints must not instantiate legacy Vnstock.
        Uses the shared fixture server so it doesn't disturb the runtime state.
        """
        url, fake_rt = closure_service_url
        with patch(
            "vnstock.Vnstock",
            side_effect=RuntimeError("legacy Vnstock must not be called"),
        ):
            status, body = _fetch(f"{url}/v1/equity/ohlcv?symbol=VNM")

        assert status == 200, f"Expected 200, got {status}: {body}"


class TestServiceResponseEnvelope:
    """Phase 4 – Service response uses data/meta/diagnostics envelope."""

    def test_response_has_data_key(self, closure_service_url):
        url, _ = closure_service_url
        _, body = _fetch(f"{url}/v1/equity/ohlcv?symbol=VNM")
        assert "data" in body

    def test_response_has_meta_key(self, closure_service_url):
        url, _ = closure_service_url
        _, body = _fetch(f"{url}/v1/equity/ohlcv?symbol=VNM")
        assert "meta" in body

    def test_response_has_diagnostics_key(self, closure_service_url):
        url, _ = closure_service_url
        _, body = _fetch(f"{url}/v1/equity/ohlcv?symbol=VNM")
        assert "diagnostics" in body

    def test_meta_dataset_is_equity_ohlcv(self, closure_service_url):
        url, _ = closure_service_url
        _, body = _fetch(f"{url}/v1/equity/ohlcv?symbol=VNM")
        assert body["meta"]["dataset"] == "equity.ohlcv"

    def test_meta_runtime_path_is_plugin_runtime(self, closure_service_url):
        url, _ = closure_service_url
        _, body = _fetch(f"{url}/v1/equity/ohlcv?symbol=VNM")
        assert body["meta"]["runtime_path"] == "plugin_runtime"


class TestServiceProviderEndpoints:
    """Phase 4 – Provider endpoints use plugin registry output."""

    def test_providers_list_returns_200(self, closure_service_url):
        url, _ = closure_service_url
        status, body = _fetch(f"{url}/v1/providers")
        assert status == 200
        assert "providers" in body

    def test_providers_is_list(self, closure_service_url):
        url, _ = closure_service_url
        _, body = _fetch(f"{url}/v1/providers")
        assert isinstance(body["providers"], list)

    def test_capabilities_returns_200(self, closure_service_url):
        url, _ = closure_service_url
        status, body = _fetch(f"{url}/v1/providers/capabilities")
        assert status == 200
        assert "capabilities" in body

    def test_capabilities_is_dict(self, closure_service_url):
        url, _ = closure_service_url
        _, body = _fetch(f"{url}/v1/providers/capabilities")
        assert isinstance(body["capabilities"], dict)


class TestServiceAuthStatus:
    """Phase 4 – Auth status endpoint works with and without auth manager."""

    def test_auth_status_returns_200(self, closure_service_url):
        url, _ = closure_service_url
        status, body = _fetch(f"{url}/v1/auth/status")
        assert status == 200
        assert "auth_status" in body

    def test_auth_status_leaks_no_secrets(self, closure_service_url):
        url, _ = closure_service_url
        _, body = _fetch(f"{url}/v1/auth/status")
        body_str = json.dumps(body).lower()
        for sensitive in ["password", "api_key", "access_token", "secret"]:
            assert sensitive not in body_str, (
                f"Sensitive field '{sensitive}' found in auth status response"
            )

    def test_auth_status_with_mock_manager(self):
        mock_manager = MagicMock()
        mock_manager.auth_status_all.return_value = [
            {
                "provider": "tcbs",
                "authenticated": True,
                "source": "local_file",
            }
        ]
        port = _get_free_port()
        stop = threading.Event()
        run_server("127.0.0.1", port, auth_manager=mock_manager, _stop_event=stop)
        time.sleep(0.15)
        status, body = _fetch(f"http://127.0.0.1:{port}/v1/auth/status")
        stop.set()
        assert status == 200
        assert "auth_status" in body

    def test_auth_status_redacts_sensitive_fields_from_manager(self):
        mock_manager = MagicMock()
        mock_manager.auth_status_all.return_value = [
            {
                "provider": "tcbs",
                "authenticated": True,
                "access_token": "secret-bearer-token-xyz",
                "password": "hunter2",
            }
        ]
        port = _get_free_port()
        stop = threading.Event()
        run_server("127.0.0.1", port, auth_manager=mock_manager, _stop_event=stop)
        time.sleep(0.15)
        _, body = _fetch(f"http://127.0.0.1:{port}/v1/auth/status")
        stop.set()
        body_str = json.dumps(body)
        assert "secret-bearer-token-xyz" not in body_str
        assert "hunter2" not in body_str


class TestServiceUnavailableEndpoints:
    """Phase 4 – Unavailable endpoint groups stay unavailable."""

    FORBIDDEN_PATHS = [
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

    @pytest.mark.parametrize("path", FORBIDDEN_PATHS)
    def test_forbidden_path_returns_404(self, closure_service_url, path):
        url, _ = closure_service_url
        status, _ = _fetch(f"{url}{path}")
        assert status == 404, f"Expected 404 for {path}, got {status}"


class TestCLIEntrypoints:
    """Phase 4 – CLI entrypoints are declared in pyproject.toml and importable."""

    def test_serve_cli_module_importable(self):
        """The serve CLI module must be importable."""
        import vnstock.cli.serve  # noqa: F401

    def test_auth_cli_module_importable(self):
        """The auth CLI module must be importable."""
        import vnstock.cli.auth  # noqa: F401

    def test_tcbs_login_cli_module_importable(self):
        """The tcbs_login CLI module must be importable."""
        import vnstock.cli.tcbs_login  # noqa: F401

    def test_serve_entrypoint_declared_in_pyproject(self):
        """vnstock-serve must be declared in pyproject.toml [project.scripts]."""
        from pathlib import Path

        import tomllib

        pyproject = Path(__file__).parent.parent.parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        scripts = data.get("project", {}).get("scripts", {})
        assert "vnstock-serve" in scripts, (
            "'vnstock-serve' not declared in pyproject.toml [project.scripts]"
        )

    def test_auth_entrypoint_declared_in_pyproject(self):
        """vnstock-auth must be declared in pyproject.toml [project.scripts]."""
        from pathlib import Path

        import tomllib

        pyproject = Path(__file__).parent.parent.parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        scripts = data.get("project", {}).get("scripts", {})
        assert "vnstock-auth" in scripts, (
            "'vnstock-auth' not declared in pyproject.toml [project.scripts]"
        )

    def test_tcbs_login_entrypoint_declared_in_pyproject(self):
        """vnstock-tcbs-login must be declared in pyproject.toml [project.scripts]."""
        from pathlib import Path

        import tomllib

        pyproject = Path(__file__).parent.parent.parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        scripts = data.get("project", {}).get("scripts", {})
        assert "vnstock-tcbs-login" in scripts, (
            "'vnstock-tcbs-login' not declared in pyproject.toml [project.scripts]"
        )
