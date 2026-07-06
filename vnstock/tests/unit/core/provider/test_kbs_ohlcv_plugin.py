"""
Tests for KBS OHLCV provider plugin and first provider path adaptation.

Tasks 69-76: Select equity.ohlcv as first provider path, add internal plugin
wrapper, route through PluginRegistry/PluginRouter, return DataFrame,
preserve provider metadata.
"""

from unittest.mock import patch

import pandas as pd
import pytest

from vnstock.core.provider.exceptions import (
    ProviderFetchError,
    UnsupportedDatasetForProviderError,
)
from vnstock.core.provider.plugin import CAPABILITY_STATUSES, ProviderPlugin
from vnstock.core.provider.plugin_registry import PluginRegistry
from vnstock.core.provider.plugin_router import PluginRouter
from vnstock.core.provider.plugins.kbs_ohlcv import KBSOHLCVPlugin


@pytest.fixture
def plugin():
    return KBSOHLCVPlugin()


@pytest.fixture
def mock_ohlcv_df():
    return pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "open": [100.0, 101.0],
            "high": [105.0, 106.0],
            "low": [99.0, 100.0],
            "close": [103.0, 104.0],
            "volume": [100000.0, 120000.0],
        }
    )


class TestKBSOHLCVPluginProtocol:
    """Plugin conforms to ProviderPlugin protocol."""

    def test_is_provider_plugin(self, plugin):
        assert isinstance(plugin, ProviderPlugin)

    def test_name_is_kbs(self, plugin):
        assert plugin.name == "KBS"

    def test_capabilities_returns_dict(self, plugin):
        caps = plugin.capabilities()
        assert isinstance(caps, dict)

    def test_equity_ohlcv_supported(self, plugin):
        caps = plugin.capabilities()
        assert caps["equity.ohlcv"]["supported"] is True

    def test_index_ohlcv_supported(self, plugin):
        caps = plugin.capabilities()
        assert caps["index.ohlcv"]["supported"] is True

    def test_capability_statuses_valid(self, plugin):
        caps = plugin.capabilities()
        for _ds, cap in caps.items():
            assert cap["status"] in CAPABILITY_STATUSES

    def test_diagnostics_returns_dict(self, plugin):
        diag = plugin.diagnostics()
        assert isinstance(diag, dict)
        assert diag["name"] == "KBS"


class TestKBSOHLCVPluginFetch:
    """Task 74-75: fetch returns DataFrame with metadata."""

    def test_fetch_equity_ohlcv_returns_dataframe(self, plugin, mock_ohlcv_df):
        """Route equity.ohlcv through KBSOHLCVPlugin → DataFrame."""
        with patch("vnstock.core.provider.plugins.kbs_ohlcv.Quote") as MockQuote:
            instance = MockQuote.return_value
            instance.history.return_value = mock_ohlcv_df

            df = plugin.fetch(
                "equity.ohlcv",
                {"symbol": "FPT", "start": "2024-01-01", "end": "2024-01-31"},
            )
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2

    def test_fetch_sets_provider_in_attrs(self, plugin, mock_ohlcv_df):
        """Task 75: provider metadata attached to df.attrs."""
        with patch("vnstock.core.provider.plugins.kbs_ohlcv.Quote") as MockQuote:
            MockQuote.return_value.history.return_value = mock_ohlcv_df
            df = plugin.fetch("equity.ohlcv", {"symbol": "FPT"})
            assert df.attrs.get("provider") == "KBS"
            assert df.attrs.get("dataset") == "equity.ohlcv"

    def test_fetch_unsupported_dataset_raises(self, plugin):
        """Task 73: Unsupported dataset raises UnsupportedDatasetForProviderError."""
        with pytest.raises(UnsupportedDatasetForProviderError) as exc_info:
            plugin.fetch("fund.nav", {"symbol": "ABC"})
        assert "KBS" in str(exc_info.value)
        assert "fund.nav" in str(exc_info.value)

    def test_fetch_provider_error_on_exception(self, plugin):
        """ProviderFetchError is raised when underlying fetch fails."""
        with patch("vnstock.core.provider.plugins.kbs_ohlcv.Quote") as MockQuote:
            MockQuote.return_value.history.side_effect = RuntimeError("network error")
            with pytest.raises(ProviderFetchError) as exc_info:
                plugin.fetch("equity.ohlcv", {"symbol": "FPT"})
            assert "KBS" in str(exc_info.value)


class TestKBSOHLCVViaRegistry:
    """Task 72: Route selected path through PluginRegistry."""

    def test_registry_resolves_kbs(self):
        registry = PluginRegistry()
        registry.register(KBSOHLCVPlugin())
        provider = registry.get("KBS")
        assert provider.name == "KBS"

    def test_registry_providers_for_equity_ohlcv(self):
        registry = PluginRegistry()
        registry.register(KBSOHLCVPlugin())
        candidates = registry.providers_for("equity.ohlcv")
        assert any(p.name == "KBS" for p in candidates)


class TestKBSOHLCVViaRouter:
    """Task 73: Route selected path through PluginRouter."""

    def test_router_resolves_kbs_auto(self):
        registry = PluginRegistry()
        registry.register(KBSOHLCVPlugin())
        router = PluginRouter(registry, default_priority=["KBS"])
        provider = router.resolve("equity.ohlcv")
        assert provider.name == "KBS"

    def test_router_resolves_kbs_explicit(self):
        registry = PluginRegistry()
        registry.register(KBSOHLCVPlugin())
        router = PluginRouter(registry)
        provider = router.resolve("equity.ohlcv", source="KBS")
        assert provider.name == "KBS"

    def test_router_then_fetch_returns_dataframe(self):
        """Full path: registry → router → plugin.fetch → DataFrame."""
        registry = PluginRegistry()
        registry.register(KBSOHLCVPlugin())
        router = PluginRouter(registry, default_priority=["KBS"])

        mock_df = pd.DataFrame(
            {
                "time": pd.to_datetime(["2024-01-01"]),
                "open": [100.0],
                "high": [105.0],
                "low": [99.0],
                "close": [103.0],
                "volume": [100000.0],
            }
        )

        with patch("vnstock.core.provider.plugins.kbs_ohlcv.Quote") as MockQuote:
            MockQuote.return_value.history.return_value = mock_df
            provider = router.resolve("equity.ohlcv")
            df = provider.fetch("equity.ohlcv", {"symbol": "FPT"})

        assert isinstance(df, pd.DataFrame)
        assert df.attrs.get("provider") == "KBS"
