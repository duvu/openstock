"""
Unit tests for PluginRouter (plugin-based provider router).
"""

import pytest

from tests.fixtures.fake_provider import FakeProviderPlugin
from vnstock.core.provider.exceptions import (
    ProviderNotFoundError,
    UnsupportedDatasetError,
    UnsupportedDatasetForProviderError,
)
from vnstock.core.provider.plugin_registry import PluginRegistry
from vnstock.core.provider.plugin_router import PluginRouter


@pytest.fixture
def registry():
    reg = PluginRegistry()
    reg.register(FakeProviderPlugin("KBS", ["equity.ohlcv", "equity.quote"]))
    reg.register(
        FakeProviderPlugin("VCI", ["equity.ohlcv", "fundamental.balance_sheet"])
    )
    reg.register(FakeProviderPlugin("TCBS", ["equity.ohlcv", "equity.quote"]))
    return reg


@pytest.fixture
def router(registry):
    return PluginRouter(registry, default_priority=["KBS", "VCI", "TCBS"])


class TestExplicitSourceRouting:
    """Tasks 44: Explicit source routing."""

    def test_explicit_known_provider(self, router):
        """Explicit source returns the named provider."""
        provider = router.resolve("equity.ohlcv", source="VCI")
        assert provider.name == "VCI"

    def test_explicit_case_insensitive(self, router):
        """Explicit source lookup is case-insensitive."""
        provider = router.resolve("equity.ohlcv", source="kbs")
        assert provider.name == "KBS"

    def test_explicit_unsupported_dataset_raises(self, router):
        """Task 46: Explicit provider that doesn't support dataset raises."""
        with pytest.raises(UnsupportedDatasetForProviderError) as exc_info:
            router.resolve("fundamental.balance_sheet", source="TCBS")
        assert "TCBS" in str(exc_info.value)
        assert "fundamental.balance_sheet" in str(exc_info.value)

    def test_explicit_unknown_provider_raises(self, router):
        """Unknown provider name raises ProviderNotFoundError."""
        with pytest.raises(ProviderNotFoundError):
            router.resolve("equity.ohlcv", source="UNKNOWN_PROVIDER")


class TestAutoRouting:
    """Tasks 45: Auto routing."""

    def test_auto_selects_first_priority_provider(self, router):
        """source=None selects highest-priority provider for the dataset."""
        provider = router.resolve("equity.ohlcv", source=None)
        assert provider.name == "KBS"

    def test_auto_string_selects_first_priority_provider(self, router):
        """source='auto' behaves the same as source=None."""
        provider = router.resolve("equity.ohlcv", source="auto")
        assert provider.name == "KBS"

    def test_auto_unsupported_dataset_raises(self, router):
        """Task 46: No provider supports the dataset raises UnsupportedDatasetError."""
        with pytest.raises(UnsupportedDatasetError, match="fund.nav"):
            router.resolve("fund.nav")

    def test_auto_priority_order_respected(self):
        """Providers are selected according to the priority list."""
        reg = PluginRegistry()
        reg.register(FakeProviderPlugin("VCI", ["equity.ohlcv"]))
        reg.register(FakeProviderPlugin("KBS", ["equity.ohlcv"]))
        # Priority: VCI first
        r = PluginRouter(reg, default_priority=["VCI", "KBS"])
        assert r.resolve("equity.ohlcv").name == "VCI"


class TestRoutingDiagnostics:
    """Task 47: Routing diagnostics."""

    def test_diagnostics_populated_after_explicit(self, router):
        """Diagnostics are available after explicit routing."""
        router.resolve("equity.ohlcv", source="KBS")
        diag = router.last_diagnostics
        assert diag is not None
        assert diag["dataset"] == "equity.ohlcv"
        assert diag["selected_provider"] == "KBS"
        assert "candidates" in diag
        assert "reason" in diag

    def test_diagnostics_populated_after_auto(self, router):
        """Diagnostics are available after auto routing."""
        router.resolve("equity.ohlcv")
        diag = router.last_diagnostics
        assert diag is not None
        assert diag["requested_source"] is None
        assert diag["selected_provider"] == "KBS"

    def test_diagnostics_schema(self, router):
        """Diagnostics include all required fields per spec."""
        router.resolve("equity.ohlcv")
        diag = router.last_diagnostics
        required_keys = {
            "dataset",
            "requested_source",
            "selected_provider",
            "candidates",
            "reason",
        }
        assert required_keys.issubset(diag.keys())
