"""
Unit tests for ProviderPlugin interface and capability shape.
"""

from tests.fixtures.fake_provider import FakeProviderPlugin
from vnstock.core.provider.plugin import CAPABILITY_STATUSES, ProviderPlugin


class TestCapabilityStatuses:
    """Task 22-23: Capability status values."""

    def test_expected_statuses_present(self):
        """All five allowed status values are defined."""
        assert {
            "stable",
            "experimental",
            "partial",
            "deprecated",
            "unsupported",
        } == CAPABILITY_STATUSES

    def test_statuses_is_frozenset(self):
        assert isinstance(CAPABILITY_STATUSES, frozenset)

    def test_no_extra_statuses(self):
        assert len(CAPABILITY_STATUSES) == 5


class TestProviderPluginProtocol:
    """Task 20-21, 23: ProviderPlugin protocol conformance."""

    def test_fake_provider_is_protocol_instance(self):
        """FakeProviderPlugin conforms to ProviderPlugin protocol."""
        plugin = FakeProviderPlugin("TEST")
        assert isinstance(plugin, ProviderPlugin)

    def test_fake_provider_has_name(self):
        plugin = FakeProviderPlugin("MY_PROVIDER")
        assert plugin.name == "MY_PROVIDER"

    def test_capabilities_returns_dict(self):
        plugin = FakeProviderPlugin("TEST")
        caps = plugin.capabilities()
        assert isinstance(caps, dict)

    def test_capabilities_contains_supported_datasets(self):
        plugin = FakeProviderPlugin("TEST", supported_datasets=["equity.ohlcv"])
        caps = plugin.capabilities()
        assert "equity.ohlcv" in caps
        assert caps["equity.ohlcv"]["supported"] is True

    def test_capability_status_is_valid(self):
        plugin = FakeProviderPlugin("TEST")
        caps = plugin.capabilities()
        for dataset, cap in caps.items():
            assert cap["status"] in CAPABILITY_STATUSES, (
                f"Invalid status '{cap['status']}' for dataset '{dataset}'"
            )

    def test_fetch_returns_dataframe(self):
        import pandas as pd

        plugin = FakeProviderPlugin("TEST")
        df = plugin.fetch("equity.ohlcv", {})
        assert isinstance(df, pd.DataFrame)

    def test_diagnostics_returns_dict(self):
        plugin = FakeProviderPlugin("TEST")
        diag = plugin.diagnostics()
        assert isinstance(diag, dict)
