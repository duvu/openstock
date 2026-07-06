"""
Plugin-based ProviderRegistry for the vnstock platform layer.

This registry manages ProviderPlugin instances (not classes).
It is distinct from the existing class-based ProviderRegistry in
``vnstock/core/registry.py``, which manages provider class lookups
for the legacy UI dispatch layer.

Usage::

    from vnstock.core.provider.plugin_registry import PluginRegistry

    registry = PluginRegistry()
    registry.register(my_provider)

    provider = registry.get("KBS")
    candidates = registry.providers_for("equity.ohlcv")
    matrix = registry.capability_matrix()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnstock.core.provider.exceptions import ProviderNotFoundError

if TYPE_CHECKING:
    from vnstock.core.provider.plugin import ProviderPlugin


class PluginRegistry:
    """Registry for provider plugin instances.

    Provider names are normalised to uppercase for case-insensitive lookup.

    Example::

        registry = PluginRegistry()
        registry.register(kbs_plugin)
        registry.register(vci_plugin)

        provider = registry.get("kbs")          # case-insensitive
        candidates = registry.providers_for("equity.ohlcv")
    """

    def __init__(self) -> None:
        # normalised_name -> plugin instance
        self._plugins: dict[str, "ProviderPlugin"] = {}

    def register(self, provider: "ProviderPlugin") -> None:
        """Register a provider plugin.

        Args:
            provider: A :class:`ProviderPlugin`-conforming instance.

        Raises:
            ValueError: If a provider with the same name is already registered.
        """
        key = provider.name.upper()
        if key in self._plugins:
            raise ValueError(
                f"Provider '{provider.name}' is already registered. "
                "Use a distinct name or deregister the existing provider first."
            )
        self._plugins[key] = provider

    def get(self, name: str) -> "ProviderPlugin":
        """Return the plugin registered under *name*.

        Args:
            name: Provider name (case-insensitive).

        Returns:
            The matching :class:`ProviderPlugin`.

        Raises:
            ProviderNotFoundError: If no provider with that name is registered.
        """
        key = name.upper()
        if key not in self._plugins:
            raise ProviderNotFoundError(name)
        return self._plugins[key]

    def providers_for(self, dataset: str) -> list["ProviderPlugin"]:
        """Return all providers that declare support for *dataset*.

        Args:
            dataset: Dotted dataset name, e.g. ``"equity.ohlcv"``.

        Returns:
            List of :class:`ProviderPlugin` instances that declare
            ``supported: True`` for *dataset*, in registration order.
        """
        result = []
        for plugin in self._plugins.values():
            caps = plugin.capabilities()
            cap = caps.get(dataset)
            if cap and cap.get("supported", False):
                result.append(plugin)
        return result

    def names(self) -> list[str]:
        """Return all registered provider names (uppercase, sorted)."""
        return sorted(self._plugins)

    def capability_matrix(self) -> dict[str, Any]:
        """Return a capability matrix across all registered providers.

        Returns:
            Dict mapping provider name → capabilities dict.
            Deterministic (sorted by provider name).
        """
        return {
            name: self._plugins[name].capabilities() for name in sorted(self._plugins)
        }

    def deregister(self, name: str) -> None:
        """Remove a provider plugin (primarily for test teardown).

        Args:
            name: Provider name (case-insensitive).

        Raises:
            ProviderNotFoundError: If the provider is not registered.
        """
        key = name.upper()
        if key not in self._plugins:
            raise ProviderNotFoundError(name)
        del self._plugins[key]

    def clear(self) -> None:
        """Remove all registered providers. For testing only."""
        self._plugins.clear()

    def __len__(self) -> int:
        return len(self._plugins)

    def __contains__(self, name: str) -> bool:
        return name.upper() in self._plugins
