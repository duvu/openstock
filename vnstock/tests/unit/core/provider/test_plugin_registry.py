"""
Unit tests for PluginRegistry (plugin-based provider registry).
"""

import pytest

from tests.fixtures.fake_provider import FakeProviderPlugin
from vnstock.core.provider.exceptions import ProviderNotFoundError
from vnstock.core.provider.plugin_registry import PluginRegistry


@pytest.fixture
def registry():
    return PluginRegistry()


@pytest.fixture
def populated_registry():
    reg = PluginRegistry()
    reg.register(FakeProviderPlugin("KBS", ["equity.ohlcv", "equity.quote"]))
    reg.register(
        FakeProviderPlugin("VCI", ["equity.ohlcv", "fundamental.balance_sheet"])
    )
    reg.register(FakeProviderPlugin("DNSE", ["equity.ohlcv"]))
    return reg


class TestPluginRegistryBasics:
    """Tasks 25-32: PluginRegistry core behaviour."""

    def test_register_and_get(self, registry):
        """Task 33: Register then retrieve by name."""
        plugin = FakeProviderPlugin("KBS")
        registry.register(plugin)
        assert registry.get("KBS") is plugin

    def test_get_case_insensitive(self, registry):
        """Task 31: Provider names are case-insensitive."""
        registry.register(FakeProviderPlugin("KBS"))
        assert registry.get("kbs") is registry.get("KBS")
        assert registry.get("Kbs") is registry.get("KBS")

    def test_duplicate_registration_raises(self, registry):
        """Task 32: Duplicate provider names raise ValueError."""
        registry.register(FakeProviderPlugin("KBS"))
        with pytest.raises(ValueError, match="already registered"):
            registry.register(FakeProviderPlugin("KBS"))

    def test_get_unknown_raises(self, registry):
        """Task 33: Unknown provider raises ProviderNotFoundError."""
        with pytest.raises(ProviderNotFoundError):
            registry.get("UNKNOWN")

    def test_names_sorted(self, populated_registry):
        """names() returns sorted uppercase provider names."""
        assert populated_registry.names() == ["DNSE", "KBS", "VCI"]

    def test_len(self, registry):
        assert len(registry) == 0
        registry.register(FakeProviderPlugin("X"))
        assert len(registry) == 1

    def test_contains(self, registry):
        registry.register(FakeProviderPlugin("ABC"))
        assert "ABC" in registry
        assert "abc" in registry  # case-insensitive
        assert "MISSING" not in registry

    def test_clear(self, populated_registry):
        populated_registry.clear()
        assert len(populated_registry) == 0


class TestProvidersFor:
    """Task 34: Dataset candidate lookup."""

    def test_providers_for_shared_dataset(self, populated_registry):
        """All providers supporting equity.ohlcv are returned."""
        candidates = populated_registry.providers_for("equity.ohlcv")
        names = {p.name for p in candidates}
        assert names == {"KBS", "VCI", "DNSE"}

    def test_providers_for_exclusive_dataset(self, populated_registry):
        """Only VCI supports fundamental.balance_sheet."""
        candidates = populated_registry.providers_for("fundamental.balance_sheet")
        names = {p.name for p in candidates}
        assert names == {"VCI"}

    def test_providers_for_unknown_dataset(self, populated_registry):
        """Unknown dataset returns empty list, not an error."""
        candidates = populated_registry.providers_for("nonexistent.dataset")
        assert candidates == []


class TestCapabilityMatrix:
    """Task 35: capability_matrix output."""

    def test_matrix_keys_are_sorted(self, populated_registry):
        matrix = populated_registry.capability_matrix()
        assert list(matrix.keys()) == sorted(matrix.keys())

    def test_matrix_contains_all_providers(self, populated_registry):
        matrix = populated_registry.capability_matrix()
        assert set(matrix.keys()) == {"KBS", "VCI", "DNSE"}

    def test_matrix_is_deterministic(self, populated_registry):
        m1 = populated_registry.capability_matrix()
        m2 = populated_registry.capability_matrix()
        assert m1 == m2
