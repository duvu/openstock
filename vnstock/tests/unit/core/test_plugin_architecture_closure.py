"""
Closure test suite for Phase 1 (core contracts + plugin foundation) and
Phase 3 (health-aware + auth-aware routing).

These tests confirm that the plugin architecture components are present,
behave as specified, and cannot be silently broken by refactors.

No live provider calls are made. All tests use FakeProviderPlugin or
InMemoryProviderHealthStore.
"""

from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
import pytest

from tests.fixtures.fake_provider import FakeProviderPlugin
from vnstock.core.auth.policies import AuthPolicy
from vnstock.core.contracts import CONTRACT_REGISTRY
from vnstock.core.provider.exceptions import (
    NoHealthyProviderError,
    ProviderDisabledError,
    ProviderInCooldownError,
    ProviderNotFoundError,
    UnsupportedDatasetError,
    UnsupportedDatasetForProviderError,
)
from vnstock.core.provider.health import (
    HealthStatus,
    InMemoryProviderHealthStore,
    ProviderHealth,
)
from vnstock.core.provider.plugin import CAPABILITY_STATUSES, ProviderPlugin
from vnstock.core.provider.plugin_registry import PluginRegistry
from vnstock.core.provider.plugin_router import PluginRouter
from vnstock.core.provider.routing import RoutingPolicy
from vnstock.core.result import _FORBIDDEN_METADATA_KEYS, DataResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KNOWN_DATASETS = {
    "equity.ohlcv",
    "equity.quote",
    "equity.intraday_trades",
    "index.ohlcv",
    "reference.symbols",
    "reference.company_info",
    "fundamental.balance_sheet",
    "fundamental.income_statement",
    "fundamental.cash_flow",
    "fundamental.financial_ratio",
    "fund.nav",
    "foreign_flow.daily",
}


def _make_registry(*names: str, datasets: list[str] | None = None) -> PluginRegistry:
    reg = PluginRegistry()
    for n in names:
        reg.register(FakeProviderPlugin(n, supported_datasets=datasets))
    return reg


def _make_router(
    registry: PluginRegistry,
    store: InMemoryProviderHealthStore | None = None,
    policy: RoutingPolicy | None = None,
) -> PluginRouter:
    return PluginRouter(
        registry=registry,
        health_store=store if store is not None else InMemoryProviderHealthStore(),
        policy=policy or RoutingPolicy.default(),
    )


# ===========================================================================
# Phase 1: Core contracts and plugin foundation
# ===========================================================================


class TestProviderPluginProtocol:
    """Phase 1 – ProviderPlugin protocol is the canonical interface."""

    def test_fake_provider_satisfies_protocol(self):
        p = FakeProviderPlugin("FAKE")
        assert isinstance(p, ProviderPlugin)

    def test_capability_statuses_is_frozenset(self):
        assert isinstance(CAPABILITY_STATUSES, frozenset)

    def test_capability_statuses_contains_required_values(self):
        required = {"stable", "experimental", "partial", "deprecated", "unsupported"}
        assert required <= CAPABILITY_STATUSES

    def test_provider_has_name_attribute(self):
        p = FakeProviderPlugin("MYPROVIDER")
        assert p.name == "MYPROVIDER"

    def test_capabilities_returns_dict(self):
        p = FakeProviderPlugin("FAKE")
        caps = p.capabilities()
        assert isinstance(caps, dict)

    def test_capabilities_fields_present(self):
        p = FakeProviderPlugin("FAKE")
        caps = p.capabilities()
        for ds, cap in caps.items():
            assert "supported" in cap, f"Missing 'supported' in {ds}"
            assert "status" in cap, f"Missing 'status' in {ds}"

    def test_capabilities_status_values_valid(self):
        p = FakeProviderPlugin("FAKE")
        for ds, cap in p.capabilities().items():
            assert cap["status"] in CAPABILITY_STATUSES, (
                f"Invalid status '{cap['status']}' for {ds}"
            )

    def test_diagnostics_returns_dict(self):
        p = FakeProviderPlugin("FAKE")
        d = p.diagnostics()
        assert isinstance(d, dict)

    def test_auth_spec_returns_spec(self):
        from vnstock.core.auth.spec import AuthSpec

        p = FakeProviderPlugin("FAKE")
        spec = p.auth_spec("equity.ohlcv")
        assert isinstance(spec, AuthSpec)

    def test_fetch_unsupported_raises(self):
        p = FakeProviderPlugin("FAKE", supported_datasets=["equity.ohlcv"])
        with pytest.raises(UnsupportedDatasetForProviderError):
            p.fetch("equity.quote", {})


class TestPluginRegistry:
    """Phase 1 – PluginRegistry manages plugin instances."""

    def test_register_and_get(self):
        reg = PluginRegistry()
        p = FakeProviderPlugin("KBS")
        reg.register(p)
        assert reg.get("KBS") is p

    def test_get_is_case_insensitive(self):
        reg = PluginRegistry()
        p = FakeProviderPlugin("KBS")
        reg.register(p)
        assert reg.get("kbs") is p
        assert reg.get("Kbs") is p

    def test_register_duplicate_raises(self):
        reg = PluginRegistry()
        reg.register(FakeProviderPlugin("KBS"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(FakeProviderPlugin("KBS"))

    def test_get_missing_raises(self):
        reg = PluginRegistry()
        with pytest.raises(ProviderNotFoundError):
            reg.get("UNKNOWN")

    def test_providers_for_returns_supporting_plugins(self):
        reg = _make_registry("A", "B")
        reg.register(FakeProviderPlugin("C", supported_datasets=["equity.quote"]))
        candidates = reg.providers_for("equity.ohlcv")
        names = [p.name for p in candidates]
        assert "A" in names
        assert "B" in names
        assert "C" not in names

    def test_providers_for_empty_if_none_support(self):
        reg = _make_registry("A")
        assert reg.providers_for("fund.nav") == []

    def test_capability_matrix_is_deterministic(self):
        reg = _make_registry("B", "A", "C")
        matrix = reg.capability_matrix()
        keys = list(matrix.keys())
        assert keys == sorted(keys)

    def test_capability_matrix_contains_all_providers(self):
        reg = _make_registry("A", "B")
        matrix = reg.capability_matrix()
        assert "A" in matrix
        assert "B" in matrix

    def test_names_sorted(self):
        reg = _make_registry("C", "A", "B")
        assert reg.names() == ["A", "B", "C"]

    def test_len(self):
        reg = _make_registry("A", "B")
        assert len(reg) == 2

    def test_contains(self):
        reg = _make_registry("KBS")
        assert "KBS" in reg
        assert "kbs" in reg
        assert "UNKNOWN" not in reg

    def test_deregister(self):
        reg = _make_registry("KBS")
        reg.deregister("KBS")
        assert "KBS" not in reg

    def test_deregister_missing_raises(self):
        reg = PluginRegistry()
        with pytest.raises(ProviderNotFoundError):
            reg.deregister("MISSING")

    def test_clear(self):
        reg = _make_registry("A", "B")
        reg.clear()
        assert len(reg) == 0


class TestDataResult:
    """Phase 1 – DataResult is the canonical internal result envelope."""

    def _make(self, **kwargs: Any) -> DataResult:
        defaults: dict[str, Any] = {
            "dataset": "equity.ohlcv",
            "provider": "KBS",
            "data": pd.DataFrame({"a": [1, 2]}),
        }
        defaults.update(kwargs)
        return DataResult(**defaults)

    def test_construction(self):
        r = self._make()
        assert r.dataset == "equity.ohlcv"
        assert r.provider == "KBS"

    def test_to_dataframe_returns_dataframe(self):
        r = self._make()
        df = r.to_dataframe()
        assert isinstance(df, pd.DataFrame)

    def test_to_dataframe_sets_dataset_attr(self):
        r = self._make()
        df = r.to_dataframe()
        assert df.attrs["dataset"] == "equity.ohlcv"

    def test_to_dataframe_sets_provider_attr(self):
        r = self._make()
        df = r.to_dataframe()
        assert df.attrs["provider"] == "KBS"

    def test_to_dataframe_sets_quality_status(self):
        r = self._make(quality_status="PASS")
        df = r.to_dataframe()
        assert df.attrs["quality_status"] == "PASS"

    def test_to_dataframe_sets_fetched_at(self):
        ts = datetime.datetime(2026, 1, 1)
        r = self._make(fetched_at=ts)
        df = r.to_dataframe()
        assert df.attrs["fetched_at"] == ts

    def test_to_dataframe_sets_diagnostics(self):
        diag = {"routing": "direct"}
        r = self._make(diagnostics=diag)
        df = r.to_dataframe()
        assert df.attrs["diagnostics"] == diag

    def test_to_dataframe_sets_quality_attr_alias(self):
        report = {"checks": []}
        r = self._make(quality_report=report)
        df = r.to_dataframe()
        assert df.attrs["quality"] == report

    def test_forbidden_metadata_keys(self):
        assert "password" in _FORBIDDEN_METADATA_KEYS
        assert "api_key" in _FORBIDDEN_METADATA_KEYS
        assert "access_token" in _FORBIDDEN_METADATA_KEYS
        assert "refresh_token" in _FORBIDDEN_METADATA_KEYS
        assert "cookie" in _FORBIDDEN_METADATA_KEYS
        assert "authorization" in _FORBIDDEN_METADATA_KEYS


class TestDatasetContractRegistry:
    """Phase 1 – Initial dataset contracts are registered."""

    REQUIRED_DATASETS = [
        "equity.ohlcv",
        "equity.quote",
        "equity.intraday_trades",
        "index.ohlcv",
        "reference.symbols",
        "reference.company_info",
        "fundamental.balance_sheet",
        "fundamental.income_statement",
        "fundamental.cash_flow",
        "fundamental.financial_ratio",
        "fund.nav",
    ]

    @pytest.mark.parametrize("dataset", REQUIRED_DATASETS)
    def test_dataset_is_registered(self, dataset: str):
        assert CONTRACT_REGISTRY.get(dataset) is not None, (
            f"Contract for '{dataset}' is not registered in CONTRACT_REGISTRY"
        )

    def test_contract_has_required_columns(self):
        contract = CONTRACT_REGISTRY.get("equity.ohlcv")
        assert hasattr(contract, "required_columns")
        assert len(contract.required_columns) > 0

    def test_equity_ohlcv_required_columns_include_basics(self):
        contract = CONTRACT_REGISTRY.get("equity.ohlcv")
        for col in ("time", "open", "high", "low", "close", "volume"):
            assert col in contract.required_columns, (
                f"'{col}' missing from equity.ohlcv required_columns"
            )


# ===========================================================================
# Phase 3: Health-aware and auth-aware routing
# ===========================================================================


class TestAutoRoutingHealthAware:
    """Phase 3 – Auto routing selects providers by health tier."""

    def test_auto_routing_picks_healthy_provider(self):
        reg = _make_registry("A")
        store = InMemoryProviderHealthStore()
        store.record_success("A", "equity.ohlcv")
        router = _make_router(reg, store=store)
        provider = router.resolve("equity.ohlcv")
        assert provider.name == "A"

    def test_auto_routing_prefers_healthy_over_degraded(self):
        reg = _make_registry("HEALTHY", "DEGRADED")
        store = InMemoryProviderHealthStore()
        store.record_success("HEALTHY", "equity.ohlcv")
        # One failure on a HEALTHY provider transitions to DEGRADED
        store.record_success("DEGRADED", "equity.ohlcv")
        store.record_failure("DEGRADED", "equity.ohlcv")
        router = _make_router(reg, store=store)
        provider = router.resolve("equity.ohlcv")
        assert provider.name == "HEALTHY"

    def test_degraded_used_as_fallback_when_no_healthy(self):
        reg = _make_registry("DEGRADED")
        store = InMemoryProviderHealthStore()
        # One failure after success → DEGRADED
        store.record_success("DEGRADED", "equity.ohlcv")
        store.record_failure("DEGRADED", "equity.ohlcv")
        router = _make_router(reg, store=store)
        provider = router.resolve("equity.ohlcv")
        assert provider.name == "DEGRADED"
        assert router.last_decision is not None
        assert router.last_decision.fallback is True

    def test_failing_excluded_by_default(self):
        reg = _make_registry("FAILING")
        store = InMemoryProviderHealthStore()
        # Force FAILING status via repeated failures
        for _ in range(5):
            store.record_failure("FAILING", "equity.ohlcv", failure_threshold=3)
        router = _make_router(reg, store=store)
        with pytest.raises(NoHealthyProviderError):
            router.resolve("equity.ohlcv")

    def test_failing_allowed_when_policy_permits(self):
        reg = _make_registry("FAILING")
        store = InMemoryProviderHealthStore()
        for _ in range(5):
            store.record_failure("FAILING", "equity.ohlcv", failure_threshold=3)
        # Allow failing fallback AND ignore cooldown
        policy = RoutingPolicy(allow_failing_fallback=True, respect_cooldown=False)
        router = _make_router(reg, store=store, policy=policy)
        provider = router.resolve("equity.ohlcv")
        assert provider.name == "FAILING"

    def test_disabled_never_selected(self):
        reg = _make_registry("DISABLED")
        store = InMemoryProviderHealthStore()
        store.set(
            ProviderHealth(
                provider="DISABLED",
                dataset="equity.ohlcv",
                status=HealthStatus.DISABLED,
            )
        )
        router = _make_router(reg, store=store)
        with pytest.raises(NoHealthyProviderError):
            router.resolve("equity.ohlcv")

    def test_no_registered_provider_raises_unsupported_dataset(self):
        reg = PluginRegistry()
        router = _make_router(reg)
        with pytest.raises(UnsupportedDatasetError):
            router.resolve("equity.ohlcv")

    def test_cooldown_is_honored(self):
        reg = _make_registry("COOLED")
        store = InMemoryProviderHealthStore()
        # Enter cooldown by exhausting failures
        for _ in range(10):
            store.record_failure(
                "COOLED", "equity.ohlcv", failure_threshold=3, cooldown_seconds=3600
            )
        assert store.get("COOLED", "equity.ohlcv").is_in_cooldown()
        router = _make_router(reg, store=store)
        with pytest.raises(NoHealthyProviderError):
            router.resolve("equity.ohlcv")


class TestExplicitRouting:
    """Phase 3 – Explicit provider selection."""

    def test_explicit_source_returns_correct_provider(self):
        reg = _make_registry("A", "B")
        router = _make_router(reg)
        p = router.resolve("equity.ohlcv", source="B")
        assert p.name == "B"

    def test_explicit_disabled_raises(self):
        reg = _make_registry("KBS")
        store = InMemoryProviderHealthStore()
        store.set(
            ProviderHealth(
                provider="KBS",
                dataset="equity.ohlcv",
                status=HealthStatus.DISABLED,
            )
        )
        router = _make_router(reg, store=store)
        with pytest.raises(ProviderDisabledError):
            router.resolve("equity.ohlcv", source="KBS")

    def test_explicit_cooldown_raises_when_policy_respects(self):
        reg = _make_registry("KBS")
        store = InMemoryProviderHealthStore()
        for _ in range(10):
            store.record_failure(
                "KBS", "equity.ohlcv", failure_threshold=3, cooldown_seconds=3600
            )
        router = _make_router(reg, store=store)
        with pytest.raises(ProviderInCooldownError):
            router.resolve("equity.ohlcv", source="KBS")

    def test_explicit_degraded_still_returns_provider(self):
        reg = _make_registry("KBS")
        store = InMemoryProviderHealthStore()
        store.set(
            ProviderHealth(
                provider="KBS",
                dataset="equity.ohlcv",
                status=HealthStatus.DEGRADED,
            )
        )
        router = _make_router(reg, store=store)
        p = router.resolve("equity.ohlcv", source="KBS")
        assert p.name == "KBS"

    def test_explicit_degraded_adds_warnings_to_decision(self):
        reg = _make_registry("KBS")
        store = InMemoryProviderHealthStore()
        store.set(
            ProviderHealth(
                provider="KBS",
                dataset="equity.ohlcv",
                status=HealthStatus.DEGRADED,
            )
        )
        router = _make_router(reg, store=store)
        router.resolve("equity.ohlcv", source="KBS")
        assert router.last_decision is not None
        assert len(router.last_decision.warnings) > 0

    def test_explicit_unsupported_dataset_raises(self):
        reg = _make_registry("KBS", datasets=["equity.ohlcv"])
        router = _make_router(reg)
        with pytest.raises(UnsupportedDatasetForProviderError):
            router.resolve("equity.quote", source="KBS")


class TestRoutingDecision:
    """Phase 3 – Routing decisions contain required fields."""

    def test_decision_has_selected_provider(self):
        reg = _make_registry("KBS")
        router = _make_router(reg)
        router.resolve("equity.ohlcv")
        d = router.last_decision
        assert d is not None
        assert d.selected_provider == "KBS"

    def test_decision_has_candidates(self):
        reg = _make_registry("KBS", "VCI")
        router = _make_router(reg)
        router.resolve("equity.ohlcv")
        d = router.last_decision
        assert d is not None
        assert "KBS" in d.candidates or "VCI" in d.candidates

    def test_decision_serializes_to_dict(self):
        reg = _make_registry("KBS")
        router = _make_router(reg)
        router.resolve("equity.ohlcv")
        d = router.last_decision
        assert d is not None
        serialized = d.to_dict()
        assert isinstance(serialized, dict)
        assert "selected_provider" in serialized
        assert "candidates" in serialized
        assert "reason" in serialized

    def test_decision_fallback_false_for_healthy(self):
        reg = _make_registry("KBS")
        router = _make_router(reg)
        router.resolve("equity.ohlcv")
        d = router.last_decision
        assert d is not None
        assert d.fallback is False


class TestHealthRecording:
    """Phase 3 – record_success and record_failure update health state."""

    def test_record_success_transitions_to_healthy(self):
        store = InMemoryProviderHealthStore()
        store.record_success("KBS", "equity.ohlcv")
        h = store.get("KBS", "equity.ohlcv")
        assert h.status == HealthStatus.HEALTHY

    def test_record_failure_increments_failure_count(self):
        store = InMemoryProviderHealthStore()
        store.record_failure("VCI", "equity.ohlcv")
        h = store.get("VCI", "equity.ohlcv")
        assert h.failure_count >= 1

    def test_record_success_resets_failure_count(self):
        store = InMemoryProviderHealthStore()
        store.record_failure("KBS", "equity.ohlcv")
        store.record_success("KBS", "equity.ohlcv")
        h = store.get("KBS", "equity.ohlcv")
        assert h.failure_count == 0

    def test_router_record_success_delegates_to_store(self):
        reg = _make_registry("KBS")
        store = InMemoryProviderHealthStore()
        router = _make_router(reg, store=store)
        router.record_success("KBS", "equity.ohlcv", latency_ms=50.0)
        assert store.get("KBS", "equity.ohlcv").status == HealthStatus.HEALTHY

    def test_router_record_failure_delegates_to_store(self):
        reg = _make_registry("KBS")
        store = InMemoryProviderHealthStore()
        router = _make_router(reg, store=store)
        router.record_failure("KBS", "equity.ohlcv")
        assert store.get("KBS", "equity.ohlcv").failure_count >= 1


class TestAuthPolicyRouting:
    """Phase 3 – Auth policy filters affect provider selection."""

    class _PublicProvider:
        """Fake provider that returns no-auth spec."""

        name = "PUBLIC"

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
            return pd.DataFrame(columns=["symbol"])

        def validate_params(self, dataset: str, params: dict) -> None:
            pass

        def diagnostics(self) -> dict:
            return {"name": "PUBLIC"}

        def auth_spec(self, dataset: str):
            from vnstock.core.auth.spec import AuthSpec

            return AuthSpec.no_auth()

    class _AuthProvider:
        """Fake provider that requires authentication."""

        name = "AUTHP"

        def capabilities(self) -> dict:
            return {
                "equity.ohlcv": {
                    "supported": True,
                    "status": "stable",
                    "auth_required": True,
                    "intervals": [],
                }
            }

        def fetch(self, dataset: str, params: dict) -> pd.DataFrame:
            return pd.DataFrame(columns=["symbol"])

        def validate_params(self, dataset: str, params: dict) -> None:
            pass

        def diagnostics(self) -> dict:
            return {"name": "AUTHP"}

        def auth_spec(self, dataset: str):
            from vnstock.core.auth.spec import AuthSpec
            from vnstock.core.auth.types import AuthType

            return AuthSpec(auth_type=AuthType.BEARER_TOKEN)

    def _make_mixed_registry(self) -> PluginRegistry:
        reg = PluginRegistry()
        reg.register(self._PublicProvider())
        reg.register(self._AuthProvider())
        return reg

    def test_prefer_no_auth_orders_public_first(self):
        reg = self._make_mixed_registry()
        router = _make_router(reg)
        provider = router.resolve("equity.ohlcv", auth_policy=AuthPolicy.PREFER_NO_AUTH)
        assert provider.name == "PUBLIC"

    def test_forbid_authenticated_excludes_auth_providers(self):
        reg = self._make_mixed_registry()
        router = _make_router(reg)
        provider = router.resolve(
            "equity.ohlcv", auth_policy=AuthPolicy.FORBID_AUTHENTICATED
        )
        assert provider.name == "PUBLIC"

    def test_require_authenticated_excludes_public_providers(self):
        reg = self._make_mixed_registry()
        router = _make_router(reg)
        provider = router.resolve(
            "equity.ohlcv", auth_policy=AuthPolicy.REQUIRE_AUTHENTICATED
        )
        assert provider.name == "AUTHP"

    def test_forbid_authenticated_rejects_auth_in_decision(self):
        reg = self._make_mixed_registry()
        router = _make_router(reg)
        router.resolve("equity.ohlcv", auth_policy=AuthPolicy.FORBID_AUTHENTICATED)
        d = router.last_decision
        assert d is not None
        assert "AUTHP" in d.rejected
