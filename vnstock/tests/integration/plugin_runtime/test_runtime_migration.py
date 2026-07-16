"""
Integration tests for the plugin runtime migration.

Tests that:
- PluginRuntime can fetch datasets using real provider plugins (mocked fetch)
- Public UI methods (Market/equity) route through PluginRuntime with fallback
- Legacy dispatch still works for non-migrated methods
- DataResult attrs are attached correctly end-to-end
- Migrated datasets do NOT silently use legacy dispatch when runtime is available
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from tests.fixtures.fake_provider import FakeProviderPlugin
from vnstock.core.provider.health import InMemoryProviderHealthStore
from vnstock.core.provider.plugin_registry import PluginRegistry
from vnstock.core.result import DataResult
from vnstock.core.runtime.bootstrap import default_plugin_registry
from vnstock.core.runtime.plugin_runtime import PluginRuntime

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_ohlcv_df(symbol: str = "FPT") -> pd.DataFrame:
    """Return a minimal OHLCV DataFrame."""
    return pd.DataFrame(
        {
            "symbol": [symbol] * 3,
            "time": pd.date_range("2024-01-01", periods=3, freq="D"),
            "open": [10.0, 11.0, 12.0],
            "high": [11.0, 12.0, 13.0],
            "low": [9.5, 10.5, 11.5],
            "close": [10.5, 11.5, 12.5],
            "volume": [100_000, 120_000, 110_000],
        }
    )


# ---------------------------------------------------------------------------
# PluginRuntime integration
# ---------------------------------------------------------------------------


class TestPluginRuntimeIntegration:
    def test_fetch_returns_dataframe(self):
        """Full runtime path with a fake provider returns a DataFrame."""
        reg = PluginRegistry()
        fake = FakeProviderPlugin("MYFAKE", ["equity.ohlcv"])
        reg.register(fake)
        store = InMemoryProviderHealthStore()
        rt = PluginRuntime(registry=reg, health_store=store)

        df = rt.fetch("equity.ohlcv", {"symbol": "FPT"})
        assert isinstance(df, pd.DataFrame)
        assert df.attrs.get("provider") == "MYFAKE"
        assert df.attrs.get("dataset") == "equity.ohlcv"

    def test_fetch_with_real_data_provider(self):
        """FakeProvider returns expected columns."""
        reg = PluginRegistry()
        reg.register(FakeProviderPlugin("KBS_FAKE", ["equity.ohlcv"]))
        store = InMemoryProviderHealthStore()
        rt = PluginRuntime(registry=reg, health_store=store)

        df = rt.fetch("equity.ohlcv", {"symbol": "VCB"})
        # FakeProviderPlugin returns all 7 columns
        for col in ["symbol", "time", "open", "high", "low", "close", "volume"]:
            assert col in df.columns

    def test_return_result_contains_routing_diagnostics(self):
        """DataResult.diagnostics must include routing information."""
        reg = PluginRegistry()
        reg.register(FakeProviderPlugin("ALPHA"))
        store = InMemoryProviderHealthStore()
        rt = PluginRuntime(registry=reg, health_store=store)

        result = rt.fetch("equity.ohlcv", {}, return_result=True)
        assert isinstance(result, DataResult)
        diag = result.diagnostics or {}
        assert "routing" in diag
        assert diag["routing"]["selected_provider"] == "ALPHA"

    def test_health_updated_on_success(self):
        """Success increments success_count in the health store."""
        store = InMemoryProviderHealthStore()
        reg = PluginRegistry()
        reg.register(FakeProviderPlugin("HEALTH_TEST"))
        rt = PluginRuntime(registry=reg, health_store=store)

        rt.fetch("equity.ohlcv", {})
        health = store.get("HEALTH_TEST", "equity.ohlcv")
        assert health.success_count == 1

    def test_health_updated_on_failure(self):
        """Failure increments failure_count in the health store."""

        class BrokenPlugin(FakeProviderPlugin):
            def fetch(self, dataset, params):
                raise RuntimeError("boom")

        store = InMemoryProviderHealthStore()
        reg = PluginRegistry()
        reg.register(BrokenPlugin("BROKEN"))
        rt = PluginRuntime(registry=reg, health_store=store)

        from vnstock.core.provider.exceptions import ProviderFetchError

        with pytest.raises(ProviderFetchError):
            rt.fetch("equity.ohlcv", {})

        health = store.get("BROKEN", "equity.ohlcv")
        assert health.failure_count == 1

    def test_dataframe_attrs_runtime_path(self):
        """runtime_path must appear in df.attrs['diagnostics']."""
        reg = PluginRegistry()
        reg.register(FakeProviderPlugin("X"))
        store = InMemoryProviderHealthStore()
        rt = PluginRuntime(registry=reg, health_store=store, runtime_path="test_rt")

        df = rt.fetch("equity.ohlcv", {})
        assert df.attrs.get("diagnostics", {}).get("runtime_path") == "test_rt"

    def test_no_credential_leakage_in_diagnostics(self):
        """diagnostics must not contain forbidden keys."""
        FORBIDDEN = {
            "password",
            "api_key",
            "access_token",
            "refresh_token",
            "cookie",
            "authorization",
        }
        reg = PluginRegistry()
        reg.register(FakeProviderPlugin("SAFE"))
        store = InMemoryProviderHealthStore()
        rt = PluginRuntime(registry=reg, health_store=store)

        df = rt.fetch("equity.ohlcv", {})
        flat_keys = set()
        diag = df.attrs.get("diagnostics", {})

        def _collect(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    flat_keys.add(k.lower())
                    _collect(v)

        _collect(diag)
        assert not flat_keys & FORBIDDEN


# ---------------------------------------------------------------------------
# _plugin_dispatch integration
# ---------------------------------------------------------------------------


class TestPluginDispatchIntegration:
    def test_plugin_dispatch_returns_dataframe(self):
        """_plugin_dispatch uses default_runtime to fetch data."""
        from vnstock.ui._base import BaseUI

        # Patch default_runtime to use our fake runtime
        store = InMemoryProviderHealthStore()
        reg = PluginRegistry()
        reg.register(FakeProviderPlugin("PATCH"))
        fake_rt = PluginRuntime(registry=reg, health_store=store)

        ui = BaseUI()
        with patch("vnstock.core.runtime.default_runtime", return_value=fake_rt):
            df = ui._plugin_dispatch("equity.ohlcv", {"symbol": "FPT"})
        assert isinstance(df, pd.DataFrame)

    def test_plugin_dispatch_compat_fallback_only_on_capability_absence(self):
        """allow_legacy_fallback returns None only when the platform has no
        provider for the dataset AND no explicit source was requested."""
        from vnstock.ui._base import BaseUI

        # Use a runtime that will fail (no providers) -> UnsupportedDatasetError.
        reg = PluginRegistry()
        empty_rt = PluginRuntime(registry=reg)

        ui = BaseUI()
        import warnings

        with patch("vnstock.core.runtime.default_runtime", return_value=empty_rt):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = ui._plugin_dispatch(
                    "equity.ohlcv",
                    {},
                    allow_legacy_fallback=True,
                )
        assert result is None
        assert len(w) == 1
        assert "COMPAT_LEGACY_DISPATCH" in str(w[0].message)

    def test_plugin_dispatch_explicit_source_never_falls_back(self):
        """An explicitly selected provider never crosses the compat boundary,
        even when allow_legacy_fallback=True and the dataset is unsupported."""
        from vnstock.core.provider.exceptions import VnstockPlatformError
        from vnstock.ui._base import BaseUI

        reg = PluginRegistry()
        empty_rt = PluginRuntime(registry=reg)

        ui = BaseUI()
        with patch("vnstock.core.runtime.default_runtime", return_value=empty_rt):
            # Explicit source that cannot be served raises a typed platform
            # error (never returns None / never re-routes to legacy dispatch).
            with pytest.raises(VnstockPlatformError):
                ui._plugin_dispatch(
                    "equity.ohlcv",
                    {},
                    source="KBS",
                    allow_legacy_fallback=True,
                )

    def test_plugin_dispatch_no_fallback_raises(self):
        """When allow_legacy_fallback=False, capability absence re-raises typed."""
        from vnstock.core.provider.exceptions import UnsupportedDatasetError
        from vnstock.ui._base import BaseUI

        reg = PluginRegistry()
        empty_rt = PluginRuntime(registry=reg)

        ui = BaseUI()
        with patch("vnstock.core.runtime.default_runtime", return_value=empty_rt):
            with pytest.raises(UnsupportedDatasetError):
                ui._plugin_dispatch("equity.ohlcv", {}, allow_legacy_fallback=False)

    def test_plugin_dispatch_provider_failure_never_falls_back(self):
        """A provider fetch failure is a typed error, not a compat signal:
        allow_legacy_fallback=True must NOT swallow it into a legacy retry."""
        from vnstock.core.provider.exceptions import ProviderFetchError
        from vnstock.ui._base import BaseUI

        class BrokenPlugin(FakeProviderPlugin):
            def fetch(self, dataset, params):
                raise RuntimeError("provider boom")

        reg = PluginRegistry()
        reg.register(BrokenPlugin("BROKEN"))
        rt = PluginRuntime(registry=reg, health_store=InMemoryProviderHealthStore())

        ui = BaseUI()
        with patch("vnstock.core.runtime.default_runtime", return_value=rt):
            with pytest.raises(ProviderFetchError):
                ui._plugin_dispatch("equity.ohlcv", {}, allow_legacy_fallback=True)

    def test_migrated_equity_ohlcv_does_not_fall_back(self):
        """Market().equity.ohlcv routes through the runtime and surfaces typed
        failures instead of silently invoking legacy _dispatch."""
        from vnstock.core.provider.exceptions import ProviderFetchError

        class BrokenPlugin(FakeProviderPlugin):
            def fetch(self, dataset, params):
                raise RuntimeError("provider boom")

        reg = PluginRegistry()
        reg.register(BrokenPlugin("KBS"))
        rt = PluginRuntime(registry=reg, health_store=InMemoryProviderHealthStore())

        from vnstock.ui.domains.market.equity import EquityMarket

        equity = EquityMarket(symbol="FPT")
        called = {"legacy": False}

        def _fail_dispatch(*args, **kwargs):
            called["legacy"] = True
            raise AssertionError("legacy _dispatch must not be reached")

        with patch("vnstock.core.runtime.default_runtime", return_value=rt):
            with patch.object(EquityMarket, "_dispatch", _fail_dispatch):
                with pytest.raises(ProviderFetchError):
                    equity.ohlcv(source="KBS")
        assert called["legacy"] is False


class TestMigratedApiArchitecture:
    """Architecture guards: migrated canonical APIs stay fail-closed."""

    def test_equity_module_does_not_enable_legacy_fallback(self):
        """The migrated equity module must not re-introduce implicit fallback.

        A regression that sets allow_legacy_fallback=True on any migrated
        dataset would silently bypass PluginRuntime's typed failure semantics.
        """
        import inspect

        from vnstock.ui.domains.market import equity as equity_module

        source = inspect.getsource(equity_module)
        assert "allow_legacy_fallback" not in source, (
            "Migrated equity datasets must not use allow_legacy_fallback; "
            "PluginRuntime is the fail-closed boundary."
        )

    def test_equity_methods_pass_explicit_source(self):
        """Every migrated equity method delegates to _plugin_dispatch with an
        explicit source, so it can never auto-fall-back to a legacy path."""
        import inspect

        from vnstock.ui.domains.market.equity import EquityMarket

        for name in ("ohlcv", "trades", "quote"):
            src = inspect.getsource(getattr(EquityMarket, name))
            assert "_plugin_dispatch" in src, f"{name} must use _plugin_dispatch"
            assert "self._dispatch(" not in src, (
                f"{name} must not call legacy _dispatch directly"
            )


# ---------------------------------------------------------------------------
# default_plugin_registry smoke test
# ---------------------------------------------------------------------------


class TestDefaultPluginRegistryIntegration:
    def test_all_builtin_providers_registered(self):
        reg = default_plugin_registry()
        assert set(reg.names()) == {
            "KBS",
            "VCI",
            "DNSE",
            "TCBS",
            "FMARKET",
            "MSN",
            "FMP",
            "FIINQUANTX",
        }

    def test_kbs_and_vci_support_equity_ohlcv(self):
        reg = default_plugin_registry()
        supported = {p.name for p in reg.providers_for("equity.ohlcv")}
        assert "KBS" in supported
        assert "VCI" in supported

    def test_fmarket_supports_fund_nav(self):
        reg = default_plugin_registry()
        supported = {p.name for p in reg.providers_for("fund.nav")}
        assert "FMARKET" in supported

    def test_capability_matrix_keys(self):
        reg = default_plugin_registry()
        matrix = reg.capability_matrix()
        assert set(matrix.keys()) == {
            "KBS",
            "VCI",
            "DNSE",
            "TCBS",
            "FMARKET",
            "MSN",
            "FMP",
            "FIINQUANTX",
        }
