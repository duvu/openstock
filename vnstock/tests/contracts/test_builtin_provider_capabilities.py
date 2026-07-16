"""
Phase 2 closure test suite: built-in provider conformance.

Tests prove that every provider registered by default_plugin_registry():
- has a valid name
- conforms to the ProviderPlugin protocol
- returns valid capabilities() with correct field structure
- uses only allowed capability status values
- declares datasets from a known set
- rejects unsupported dataset fetches explicitly
- returns safe-to-serialize diagnostics

No live provider calls are made. All tests use registry inspection only.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from vnstock.core.provider.exceptions import (
    UnsupportedDatasetForProviderError,
)
from vnstock.core.provider.plugin import CAPABILITY_STATUSES, ProviderPlugin
from vnstock.core.runtime.bootstrap import default_plugin_registry

# ---------------------------------------------------------------------------
# Known dataset names — all datasets any built-in provider should declare
# ---------------------------------------------------------------------------

_KNOWN_DATASETS: frozenset[str] = frozenset(
    {
        "equity.ohlcv",
        "equity.quote",
        "equity.intraday_trades",
        "index.ohlcv",
        "reference.symbols",
        "reference.company_info",
        "reference.corporate_actions",
        "fundamental.balance_sheet",
        "fundamental.income_statement",
        "fundamental.cash_flow",
        "fundamental.financial_ratio",
        "fund.nav",
        "foreign_flow.daily",
    }
)

# Sensitive keys that MUST NOT appear in serialized diagnostics
_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "api_key",
        "access_token",
        "refresh_token",
        "cookie",
        "session_id",
        "authorization",
    }
)

# ---------------------------------------------------------------------------
# Registry fixture — shared across all tests in this module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def builtin_registry():
    return default_plugin_registry()


@pytest.fixture(scope="module")
def builtin_providers(builtin_registry):
    return [builtin_registry.get(name) for name in builtin_registry.names()]


# ---------------------------------------------------------------------------
# Test: provider names in registry
# ---------------------------------------------------------------------------


class TestBuiltinProviderNames:
    """Phase 2 – default_plugin_registry registers the required built-in providers."""

    REQUIRED_NAMES = {"KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"}

    def test_all_required_names_registered(self, builtin_registry):
        registered = set(builtin_registry.names())
        missing = self.REQUIRED_NAMES - registered
        assert not missing, f"Missing built-in providers: {missing}"

    def test_registry_has_at_least_seven_providers(self, builtin_registry):
        assert len(builtin_registry) >= 7

    def test_capability_matrix_is_deterministic(self, builtin_registry):
        m1 = list(builtin_registry.capability_matrix().keys())
        m2 = list(builtin_registry.capability_matrix().keys())
        assert m1 == m2 == sorted(m1)


# ---------------------------------------------------------------------------
# Test: protocol conformance per provider
# ---------------------------------------------------------------------------


class TestProviderProtocolConformance:
    """Phase 2 – every built-in provider satisfies ProviderPlugin protocol."""

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_provider_is_provider_plugin(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        assert isinstance(p, ProviderPlugin), (
            f"{provider_name} does not satisfy ProviderPlugin protocol"
        )

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_provider_name_is_uppercase_string(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        assert isinstance(p.name, str)
        assert p.name == p.name.upper(), f"Provider name '{p.name}' is not uppercase"

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_provider_has_capabilities_method(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        assert callable(getattr(p, "capabilities", None))

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_provider_has_fetch_method(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        assert callable(getattr(p, "fetch", None))

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_provider_has_validate_params_method(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        assert callable(getattr(p, "validate_params", None))

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_provider_has_diagnostics_method(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        assert callable(getattr(p, "diagnostics", None))

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_provider_has_auth_spec_method(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        assert callable(getattr(p, "auth_spec", None))


# ---------------------------------------------------------------------------
# Test: capabilities() structure
# ---------------------------------------------------------------------------


class TestCapabilitiesStructure:
    """Phase 2 – capabilities() returns valid, machine-testable declarations."""

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_capabilities_returns_dict(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        caps = p.capabilities()
        assert isinstance(caps, dict), (
            f"{provider_name}.capabilities() returned {type(caps)}"
        )

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_capabilities_not_empty(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        assert len(p.capabilities()) > 0, f"{provider_name} declares zero capabilities"

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_each_capability_has_supported_field(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        for ds, cap in p.capabilities().items():
            assert "supported" in cap, (
                f"{provider_name} capability '{ds}' missing 'supported' field"
            )

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_each_capability_has_status_field(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        for ds, cap in p.capabilities().items():
            assert "status" in cap, (
                f"{provider_name} capability '{ds}' missing 'status' field"
            )

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_capability_statuses_in_allowed_set(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        for ds, cap in p.capabilities().items():
            assert cap["status"] in CAPABILITY_STATUSES, (
                f"{provider_name} capability '{ds}' has invalid status '{cap['status']}'"
            )

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_supported_datasets_are_known(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        for ds, cap in p.capabilities().items():
            if cap.get("supported", False):
                assert ds in _KNOWN_DATASETS, (
                    f"{provider_name} declares support for unknown dataset '{ds}'"
                )


# ---------------------------------------------------------------------------
# Test: unsupported dataset rejection
# ---------------------------------------------------------------------------


class TestUnsupportedDatasetRejection:
    """Phase 2 – unsupported dataset fetches are rejected explicitly."""

    # Datasets that should NOT be supported by all providers
    _UNLIKELY_DATASET = "unknown.does_not_exist_ever"

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_fetch_unknown_dataset_raises(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        caps = p.capabilities()
        cap = caps.get(self._UNLIKELY_DATASET, {})
        if cap.get("supported", False):
            pytest.skip(
                f"{provider_name} declares support for '{self._UNLIKELY_DATASET}'"
            )
        with pytest.raises(
            (UnsupportedDatasetForProviderError, Exception),
            match=r"(?i)unsupported|not supported|unknown",
        ):
            p.fetch(self._UNLIKELY_DATASET, {})

    def test_fmarket_does_not_support_equity_ohlcv(self, builtin_registry):
        """FMarket only supports fund data; equity.ohlcv must be rejected."""
        p = builtin_registry.get("FMARKET")
        caps = p.capabilities()
        cap = caps.get("equity.ohlcv", {})
        assert not cap.get("supported", False), (
            "FMarket should NOT support equity.ohlcv"
        )


# ---------------------------------------------------------------------------
# Test: diagnostics safety
# ---------------------------------------------------------------------------


class TestDiagnosticsSafety:
    """Phase 2 – provider diagnostics are dict-like and safe to serialize."""

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_diagnostics_returns_dict(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        d = p.diagnostics()
        assert isinstance(d, dict), f"{provider_name}.diagnostics() returned {type(d)}"

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_diagnostics_json_serializable(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        d = p.diagnostics()
        try:
            json.dumps(d)
        except (TypeError, ValueError) as e:
            pytest.fail(f"{provider_name}.diagnostics() is not JSON-serializable: {e}")

    @pytest.mark.parametrize(
        "provider_name",
        ["KBS", "VCI", "DNSE", "TCBS", "FMARKET", "MSN", "FMP"],
    )
    def test_diagnostics_no_sensitive_keys(self, builtin_registry, provider_name):
        p = builtin_registry.get(provider_name)
        d = p.diagnostics()

        def _check_keys(obj: Any, path: str = "") -> None:
            """Recursively check that no dict key is a sensitive credential key."""
            if isinstance(obj, dict):
                for k, v in obj.items():
                    k_lower = k.lower()
                    assert k_lower not in _SENSITIVE_KEYS, (
                        f"{provider_name}.diagnostics() has sensitive key "
                        f"'{k}' at path '{path}/{k}'"
                    )
                    _check_keys(v, path=f"{path}/{k}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    _check_keys(item, path=f"{path}[{i}]")

        _check_keys(d)


# ---------------------------------------------------------------------------
# Test: capability matrix correctness
# ---------------------------------------------------------------------------


class TestCapabilityMatrix:
    """Phase 2 – capability matrix is deterministic and covers all providers."""

    def test_capability_matrix_keys_match_registered_names(self, builtin_registry):
        matrix = builtin_registry.capability_matrix()
        registered = set(builtin_registry.names())
        assert set(matrix.keys()) == registered

    def test_capability_matrix_values_are_dicts(self, builtin_registry):
        matrix = builtin_registry.capability_matrix()
        for name, caps in matrix.items():
            assert isinstance(caps, dict), f"Capabilities for {name} are not a dict"

    def test_providers_for_equity_ohlcv_has_at_least_one(self, builtin_registry):
        candidates = builtin_registry.providers_for("equity.ohlcv")
        assert len(candidates) >= 1, (
            "No providers support equity.ohlcv in default registry"
        )

    def test_providers_for_fund_nav_includes_fmarket(self, builtin_registry):
        candidates = builtin_registry.providers_for("fund.nav")
        names = [p.name for p in candidates]
        assert "FMARKET" in names, f"FMARKET should support fund.nav; got: {names}"
