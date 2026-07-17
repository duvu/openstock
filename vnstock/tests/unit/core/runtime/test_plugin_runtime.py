"""
Unit tests for PluginRuntime (vnstock/core/runtime/).

Covers:
- DatasetRequest construction and validation
- default_plugin_registry() provider names
- PluginRuntime basic fetch (DataFrame + DataResult)
- Health recording on success/failure
- Contract validation (pass + fail)
- Explicit source routing
- Auto routing via runtime
- DataResult attrs
- diagnostics content + no credential leakage
- runtime_path in diagnostics
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

# Ensure project root on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from tests.fixtures.fake_provider import FakeProviderPlugin
from vnstock.core.contracts.base import DatasetContract, DatasetContractRegistry
from vnstock.core.provider.exceptions import (
    DatasetContractError,
    ProviderFetchError,
)
from vnstock.core.provider.health import (
    InMemoryProviderHealthStore,
)
from vnstock.core.provider.plugin_registry import PluginRegistry
from vnstock.core.result import DataResult
from vnstock.core.runtime.bootstrap import default_plugin_registry
from vnstock.core.runtime.plugin_runtime import PluginRuntime
from vnstock.core.runtime.request import DatasetRequest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_registry(*names: str) -> PluginRegistry:
    """Create a registry pre-populated with named fake providers."""
    reg = PluginRegistry()
    for n in names:
        reg.register(FakeProviderPlugin(n))
    return reg


def _make_runtime(provider_name: str = "FAKE") -> PluginRuntime:
    reg = _minimal_registry(provider_name)
    store = InMemoryProviderHealthStore()
    return PluginRuntime(registry=reg, health_store=store)


# ---------------------------------------------------------------------------
# DatasetRequest tests
# ---------------------------------------------------------------------------


class TestDatasetRequest:
    def test_minimal_construction(self):
        req = DatasetRequest(dataset="equity.ohlcv")
        assert req.dataset == "equity.ohlcv"
        assert req.params == {}
        assert req.source is None
        assert req.validate is False
        assert req.quality_mode == "warn"
        assert req.return_result is False

    def test_full_construction(self):
        req = DatasetRequest(
            dataset="equity.ohlcv",
            params={"symbol": "FPT"},
            source="KBS",
            validate=True,
            quality_mode="strict",
            return_result=True,
        )
        assert req.dataset == "equity.ohlcv"
        assert req.params["symbol"] == "FPT"
        assert req.source == "KBS"
        assert req.validate is True
        assert req.quality_mode == "strict"
        assert req.return_result is True

    def test_empty_dataset_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            DatasetRequest(dataset="")

    def test_undotted_dataset_raises(self):
        with pytest.raises(ValueError, match="dotted name"):
            DatasetRequest(dataset="equityohlcv")

    def test_invalid_quality_mode_raises(self):
        with pytest.raises(ValueError, match="quality_mode"):
            DatasetRequest(dataset="equity.ohlcv", quality_mode="bad")

    def test_non_dict_params_raises(self):
        with pytest.raises(TypeError, match="params must be a dict"):
            DatasetRequest(dataset="equity.ohlcv", params=["symbol"])  # type: ignore


# ---------------------------------------------------------------------------
# bootstrap tests
# ---------------------------------------------------------------------------


class TestDefaultPluginRegistry:
    def test_provider_names(self):
        reg = default_plugin_registry()
        names = reg.names()
        assert set(names) == {
            "KBS",
            "VCI",
            "DNSE",
            "TCBS",
            "FMARKET",
            "MSN",
            "FMP",
            "FIINQUANTX",
        }

    def test_kbs_supports_equity_ohlcv(self):
        reg = default_plugin_registry()
        providers = reg.providers_for("equity.ohlcv")
        names = [p.name for p in providers]
        assert "KBS" in names

    def test_capability_matrix_has_all_providers(self):
        reg = default_plugin_registry()
        matrix = reg.capability_matrix()
        assert len(matrix) == 8

    def test_fresh_instances_are_independent(self):
        reg1 = default_plugin_registry()
        reg2 = default_plugin_registry()
        # Each call returns a NEW registry — they must not share state
        assert reg1 is not reg2


# ---------------------------------------------------------------------------
# PluginRuntime.fetch — basic happy path
# ---------------------------------------------------------------------------


class TestPluginRuntimeFetch:
    def test_returns_dataframe_by_default(self):
        rt = _make_runtime()
        df = rt.fetch("equity.ohlcv", {"symbol": "FPT"})
        assert isinstance(df, pd.DataFrame)

    def test_return_result_flag(self):
        rt = _make_runtime()
        result = rt.fetch("equity.ohlcv", {"symbol": "FPT"}, return_result=True)
        assert isinstance(result, DataResult)

    def test_data_result_fields(self):
        rt = _make_runtime()
        result = rt.fetch("equity.ohlcv", {}, return_result=True)
        assert result.dataset == "equity.ohlcv"
        assert result.provider == "FAKE"
        assert isinstance(result.data, pd.DataFrame)
        assert result.fetched_at is not None

    def test_fetch_request_accepts_dataset_request(self):
        rt = _make_runtime()
        req = DatasetRequest(dataset="equity.ohlcv", return_result=True)
        result = rt.fetch_request(req)
        assert isinstance(result, DataResult)

    def test_dataframe_attrs_populated(self):
        rt = _make_runtime()
        df = rt.fetch("equity.ohlcv", {"symbol": "FPT"})
        assert df.attrs.get("provider") == "FAKE"
        assert df.attrs.get("dataset") == "equity.ohlcv"

    def test_diagnostics_runtime_path(self):
        rt = _make_runtime()
        result = rt.fetch("equity.ohlcv", {}, return_result=True)
        assert result.diagnostics is not None
        assert result.diagnostics.get("runtime_path") == "plugin_runtime"

    def test_custom_runtime_path(self):
        reg = _minimal_registry("FAKE")
        store = InMemoryProviderHealthStore()
        rt = PluginRuntime(registry=reg, health_store=store, runtime_path="my_runtime")
        result = rt.fetch("equity.ohlcv", {}, return_result=True)
        assert result.diagnostics["runtime_path"] == "my_runtime"

    def test_safe_provider_lineage_is_preserved_in_diagnostics(self):
        class LineageProvider(FakeProviderPlugin):
            def fetch(self, dataset, params):
                frame = super().fetch(dataset, params)
                frame.attrs.update(
                    {
                        "sdk_version": "0.1.64",
                        "contract_version": "fiinquantx-contract-v1",
                        "source_method": "Fetch_Trading_Data",
                        "ohlcv_request_policy": {
                            "basis": "RAW_UNADJUSTED",
                            "adjusted": "requested_false",
                        },
                        "password": "must-not-leak",
                    }
                )
                return frame

        registry = PluginRegistry()
        registry.register(LineageProvider("LINEAGE"))
        runtime = PluginRuntime(registry=registry)

        result = runtime.fetch(
            "equity.ohlcv",
            {"symbol": "FPT"},
            source="LINEAGE",
            return_result=True,
        )

        assert result.diagnostics["provider_lineage"] == {
            "sdk_version": "0.1.64",
            "contract_version": "fiinquantx-contract-v1",
            "source_method": "Fetch_Trading_Data",
            "ohlcv_request_policy": {
                "basis": "RAW_UNADJUSTED",
                "adjusted": "requested_false",
            },
        }
        assert "must-not-leak" not in str(result.diagnostics)

    def test_diagnostics_contains_routing(self):
        rt = _make_runtime()
        result = rt.fetch("equity.ohlcv", {}, return_result=True)
        assert "routing" in result.diagnostics  # type: ignore[operator]

    def test_diagnostics_no_credentials(self):
        rt = _make_runtime()
        result = rt.fetch("equity.ohlcv", {}, return_result=True)
        diag = result.diagnostics or {}
        for forbidden in ("password", "api_key", "access_token", "authorization"):
            assert forbidden not in diag


# ---------------------------------------------------------------------------
# Health recording
# ---------------------------------------------------------------------------


class TestHealthRecording:
    def test_success_increments_success_count(self):
        store = InMemoryProviderHealthStore()
        reg = _minimal_registry("FAKE")
        rt = PluginRuntime(registry=reg, health_store=store)
        rt.fetch("equity.ohlcv", {})
        health = store.get("FAKE", "equity.ohlcv")
        assert health.success_count >= 1

    def test_failure_increments_failure_count(self):
        class BrokenProvider(FakeProviderPlugin):
            def fetch(self, dataset, params):
                raise RuntimeError("simulated failure")

        store = InMemoryProviderHealthStore()
        reg = PluginRegistry()
        reg.register(BrokenProvider("BROKEN"))
        rt = PluginRuntime(registry=reg, health_store=store)
        with pytest.raises(ProviderFetchError):
            rt.fetch("equity.ohlcv", {})
        health = store.get("BROKEN", "equity.ohlcv")
        assert health.failure_count >= 1

    def test_unexpected_failure_does_not_leak_cause_into_error_or_health(self):
        class BrokenProvider(FakeProviderPlugin):
            def fetch(self, dataset, params):
                raise RuntimeError("password=super-secret")

        store = InMemoryProviderHealthStore()
        reg = PluginRegistry()
        reg.register(BrokenProvider("BROKEN"))
        runtime = PluginRuntime(registry=reg, health_store=store)

        with pytest.raises(ProviderFetchError) as error:
            runtime.fetch("equity.ohlcv", {})

        health = store.get("BROKEN", "equity.ohlcv")
        assert "super-secret" not in str(error.value)
        assert "super-secret" not in (health.notes or "")


# ---------------------------------------------------------------------------
# Contract validation
# ---------------------------------------------------------------------------


class TestContractValidation:
    def _make_runtime_with_contract(
        self,
        required_columns: list[str],
        provider_name: str = "FAKE",
        *,
        dtype_rules: dict[str, str] | None = None,
        validator: str | None = None,
        frame: pd.DataFrame | None = None,
    ) -> PluginRuntime:
        if frame is None:
            reg = _minimal_registry(provider_name)
        else:

            class FrameProvider(FakeProviderPlugin):
                def fetch(self, dataset, params):
                    return frame.copy()

            reg = PluginRegistry()
            reg.register(FrameProvider(provider_name))
        store = InMemoryProviderHealthStore()
        cr = DatasetContractRegistry()
        cr.register(
            DatasetContract(
                dataset="equity.ohlcv",
                required_columns=required_columns,
                dtype_rules=dtype_rules or {},
                validator=validator,
            )
        )
        return PluginRuntime(registry=reg, contract_registry=cr, health_store=store)

    def test_passing_contract(self):
        rt = self._make_runtime_with_contract(
            ["symbol", "time", "open", "high", "low", "close", "volume"]
        )
        result = rt.fetch("equity.ohlcv", {}, validate=True, return_result=True)
        assert result.quality_status == "PASS"
        assert result.quality_report == {"contract_errors": []}

    def test_failing_contract_warn_mode(self):
        rt = self._make_runtime_with_contract(["symbol", "time", "NONEXISTENT_COL"])
        result = rt.fetch(
            "equity.ohlcv", {}, validate=True, quality_mode="warn", return_result=True
        )
        assert result.quality_status == "FAIL"
        assert result.quality_report is not None
        errors = result.quality_report.get("contract_errors", [])
        assert any("NONEXISTENT_COL" in e for e in errors)

    def test_failing_contract_strict_mode_raises(self):
        rt = self._make_runtime_with_contract(["symbol", "NONEXISTENT_COL"])
        with pytest.raises(DatasetContractError):
            rt.fetch("equity.ohlcv", {}, validate=True, quality_mode="strict")

    def test_failing_dtype_rule_strict_mode_raises(self):
        rt = self._make_runtime_with_contract(
            ["symbol"],
            dtype_rules={"symbol": "int64"},
            frame=pd.DataFrame({"symbol": ["FPT"]}),
        )

        with pytest.raises(DatasetContractError, match="dtype"):
            rt.fetch("equity.ohlcv", {}, validate=True, quality_mode="strict")

    def test_registered_validator_errors_raise_in_strict_mode(self):
        class InvalidOHLCVProvider(FakeProviderPlugin):
            def fetch(self, dataset, params):
                return pd.DataFrame(
                    {
                        "symbol": pd.Series(["FPT"], dtype="string"),
                        "time": pd.to_datetime(["2026-07-01"]),
                        "open": [10.0],
                        "high": [8.0],
                        "low": [9.0],
                        "close": [11.0],
                        "volume": [-1.0],
                    }
                )

        registry = PluginRegistry()
        registry.register(InvalidOHLCVProvider("FAKE"))
        contracts = DatasetContractRegistry()
        contracts.register(
            DatasetContract(
                dataset="equity.ohlcv",
                required_columns=[
                    "symbol",
                    "time",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ],
                dtype_rules={
                    "symbol": "string",
                    "time": "datetime64[ns]",
                    "open": "float64",
                    "high": "float64",
                    "low": "float64",
                    "close": "float64",
                    "volume": "float64",
                },
                validator="ohlcv",
            )
        )
        runtime = PluginRuntime(registry=registry, contract_registry=contracts)

        with pytest.raises(DatasetContractError, match="OHLC"):
            runtime.fetch("equity.ohlcv", {}, validate=True, quality_mode="strict")

    def test_fiinquantx_cannot_disable_strict_contract_validation(self):
        rt = self._make_runtime_with_contract(
            ["symbol"],
            provider_name="FIINQUANTX",
            dtype_rules={"symbol": "int64"},
            frame=pd.DataFrame({"symbol": ["FPT"]}),
        )

        with pytest.raises(DatasetContractError, match="dtype"):
            rt.fetch(
                "equity.ohlcv",
                {},
                source="FIINQUANTX",
                validate=False,
                quality_mode="warn",
            )

    def test_fiinquantx_membership_requires_utc_observation_dtype(self):
        class NaiveMembershipProvider(FakeProviderPlugin):
            def __init__(self):
                super().__init__(
                    "FIINQUANTX",
                    supported_datasets=["reference.index_membership_snapshot"],
                )

            def fetch(self, dataset, params):
                return pd.DataFrame(
                    {
                        "entity_id": pd.Series(["VN30"], dtype="string"),
                        "member_symbol": pd.Series(["FPT"], dtype="string"),
                        "observed_at": pd.to_datetime(["2026-07-01"]),
                    }
                )

        registry = PluginRegistry()
        registry.register(NaiveMembershipProvider())
        runtime = PluginRuntime(registry=registry)

        with pytest.raises(DatasetContractError, match=r"datetime64\[ns, UTC\]"):
            runtime.fetch(
                "reference.index_membership_snapshot",
                {"entity": "VN30"},
                source="FIINQUANTX",
                validate=False,
            )

    def test_unknown_registered_validator_is_a_typed_contract_failure(self):
        rt = self._make_runtime_with_contract(
            ["symbol"],
            validator="not_registered",
            frame=pd.DataFrame({"symbol": ["FPT"]}),
        )

        with pytest.raises(DatasetContractError, match="No validator registered"):
            rt.fetch("equity.ohlcv", {}, validate=True, quality_mode="strict")

    @pytest.mark.parametrize("provider_name", ["KBS", "FIINQUANTX"])
    def test_real_ohlcv_normalizers_pass_semantic_dtype_validation(
        self, provider_name: str
    ):
        from vnstock.providers.fiinquantx.normalize import normalize_ohlcv
        from vnstock.providers.kbs.normalize import normalize_equity_ohlcv

        class NormalizedProvider(FakeProviderPlugin):
            def fetch(self, dataset, params):
                if self.name == "KBS":
                    raw = pd.DataFrame(
                        {
                            "time": pd.to_datetime(["2026-07-01"]),
                            "open": [100.0],
                            "high": [102.0],
                            "low": [99.0],
                            "close": [101.0],
                            "volume": [1000],
                        }
                    )
                    return normalize_equity_ohlcv(raw, "FPT")
                raw = pd.DataFrame(
                    {
                        "ticker": ["FPT"],
                        "timestamp": ["2026-07-01"],
                        "open": [100.0],
                        "high": [102.0],
                        "low": [99.0],
                        "close": [101.0],
                        "volume": [1000],
                    }
                )
                return normalize_ohlcv(raw, dataset)

        registry = PluginRegistry()
        registry.register(NormalizedProvider(provider_name))
        runtime = PluginRuntime(registry=registry)

        result = runtime.fetch(
            "equity.ohlcv",
            {"symbol": "FPT", "interval": "1D"},
            source=provider_name,
            validate=True,
            quality_mode="strict",
            return_result=True,
        )

        assert result.quality_status == "PASS"

    def test_structurally_valid_empty_ohlcv_is_not_a_contract_failure(self):
        from vnstock.providers.fiinquantx.normalize import normalize_ohlcv

        class EmptyProvider(FakeProviderPlugin):
            def fetch(self, dataset, params):
                return normalize_ohlcv(pd.DataFrame(), dataset)

        registry = PluginRegistry()
        registry.register(EmptyProvider("FIINQUANTX"))
        runtime = PluginRuntime(registry=registry)

        result = runtime.fetch(
            "equity.ohlcv",
            {"symbol": "FPT", "interval": "1D"},
            source="FIINQUANTX",
            return_result=True,
        )

        assert result.quality_status == "PASS"
        assert result.data.empty

    def test_valid_empty_corporate_actions_pass_strict_validation(self):
        from vnstock.core.corporate_actions import empty_corporate_actions

        class EmptyCorporateActionProvider(FakeProviderPlugin):
            def __init__(self):
                super().__init__(
                    "VCI", supported_datasets=["reference.corporate_actions"]
                )

            def fetch(self, dataset, params):
                return empty_corporate_actions("VCI")

        registry = PluginRegistry()
        registry.register(EmptyCorporateActionProvider())
        runtime = PluginRuntime(registry=registry)

        result = runtime.fetch(
            "reference.corporate_actions",
            {"symbol": "FPT"},
            source="VCI",
            validate=True,
            quality_mode="strict",
            return_result=True,
        )

        assert result.quality_status == "PASS"
        assert result.data.empty

    def test_empty_frame_with_incompatible_contract_dtypes_fails(self):
        rt = self._make_runtime_with_contract(
            ["observed_at"],
            dtype_rules={"observed_at": "datetime64[ns, UTC]"},
            frame=pd.DataFrame(columns=["observed_at"]),
        )

        with pytest.raises(DatasetContractError, match=r"datetime64\[ns, UTC\]"):
            rt.fetch("equity.ohlcv", {}, validate=True, quality_mode="strict")

    def test_strict_contract_failures_accumulate_provider_health(self):
        store = InMemoryProviderHealthStore(failure_threshold=3, cooldown_seconds=60)
        runtime = self._make_runtime_with_contract(
            ["symbol", "missing"], provider_name="FIINQUANTX"
        )
        runtime.health_store = store
        runtime._router.health_store = store

        for _ in range(3):
            with pytest.raises(DatasetContractError):
                runtime.fetch("equity.ohlcv", {}, source="FIINQUANTX")

        health = store.get("FIINQUANTX", "equity.ohlcv")
        assert health.failure_count == 3
        assert health.success_count == 0
        assert health.is_in_cooldown()

    def test_strict_validation_fails_when_contract_is_not_registered(self):
        reg = _minimal_registry("FAKE")
        store = InMemoryProviderHealthStore()
        empty_cr = DatasetContractRegistry()
        rt = PluginRuntime(registry=reg, contract_registry=empty_cr, health_store=store)
        with pytest.raises(DatasetContractError, match="No contract registered"):
            rt.fetch("equity.ohlcv", {}, validate=True, quality_mode="strict")


# ---------------------------------------------------------------------------
# Explicit source routing
# ---------------------------------------------------------------------------


class TestExplicitSourceRouting:
    def test_explicit_source_uses_named_provider(self):
        reg = _minimal_registry("ALPHA", "BETA")
        store = InMemoryProviderHealthStore()
        rt = PluginRuntime(registry=reg, health_store=store)
        result = rt.fetch("equity.ohlcv", {}, source="BETA", return_result=True)
        assert result.provider == "BETA"

    def test_explicit_source_case_insensitive(self):
        reg = _minimal_registry("GAMMA")
        store = InMemoryProviderHealthStore()
        rt = PluginRuntime(registry=reg, health_store=store)
        result = rt.fetch("equity.ohlcv", {}, source="gamma", return_result=True)
        assert result.provider == "GAMMA"
