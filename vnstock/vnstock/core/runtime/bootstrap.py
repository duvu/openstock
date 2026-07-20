"""
Bootstrap helpers for PluginRuntime default configuration.

Provides ``default_plugin_registry()`` which creates a fresh PluginRegistry
with all eight built-in provider plugins registered.

Usage::

    from vnstock.core.runtime.bootstrap import default_plugin_registry
    from vnstock.core.runtime.plugin_runtime import PluginRuntime

    registry = default_plugin_registry()
    runtime = PluginRuntime(registry=registry)
"""

from __future__ import annotations

from vnstock.core.provider.plugin_registry import PluginRegistry


def default_plugin_registry() -> PluginRegistry:
    """Create a new PluginRegistry pre-populated with all built-in providers.

    The registry includes:

    - **KBS** — primary Vietnamese market data provider (stable)
    - **VCI** — secondary Vietnamese market data provider (stable)
    - **DNSE** — DNSE chart API (geographic restriction applies)
    - **TCBS** — TCBS market data (requires bearer token auth)
    - **FMARKET** — FMarket fund platform (fund data only)
    - **MSN** — MSN Money market data (experimental)
    - **FMP** — Financial Modeling Prep API (requires FMP_API_KEY)
    - **FIINQUANTX** — licensed FiinQuantX SDK (explicit-source only; requires
      SDK, credentials and acknowledgement)

    Returns:
        A new :class:`PluginRegistry` with all eight providers registered.
    """
    # Lazy imports avoid circular imports and pay import cost only on first use.
    from vnstock.providers.dnse.plugin import DNSEProviderPlugin
    from vnstock.providers.fiinquantx.plugin import FiinQuantXProviderPlugin
    from vnstock.providers.fmarket.plugin import FMarketProviderPlugin
    from vnstock.providers.fmp.plugin import FMPProviderPlugin
    from vnstock.providers.kbs.plugin import KBSProviderPlugin
    from vnstock.providers.msn.plugin import MSNProviderPlugin
    from vnstock.providers.tcbs.plugin import TCBSProviderPlugin
    from vnstock.providers.vci.plugin import VCIProviderPlugin

    registry = PluginRegistry()
    registry.register(KBSProviderPlugin())
    registry.register(VCIProviderPlugin())
    registry.register(DNSEProviderPlugin())
    registry.register(TCBSProviderPlugin())
    registry.register(FMarketProviderPlugin())
    registry.register(MSNProviderPlugin())
    registry.register(FMPProviderPlugin())
    registry.register(FiinQuantXProviderPlugin())
    return registry
