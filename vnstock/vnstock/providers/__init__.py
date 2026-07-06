"""
vnstock/providers — internal provider plugin package.

Each subdirectory contains a normalized provider plugin that conforms to
the Phase 1 ProviderPlugin protocol.  Existing explorer/connector code
continues to work unchanged; provider plugins are thin adapter wrappers.

Phase 2 providers: kbs, vci, dnse, tcbs, fmarket, msn, fmp.

External provider packages (vnstock-provider-*) are deferred to a later phase.

Module-level ``REGISTRY`` is a pre-populated :class:`PluginRegistry` containing
all seven built-in Phase 2 provider plugins.  Import this to resolve providers
via the Phase 1 platform layer.

Example::

    from vnstock.providers import REGISTRY

    providers = REGISTRY.providers_for("equity.ohlcv")
    matrix = REGISTRY.capability_matrix()
"""

from __future__ import annotations

from vnstock.core.provider.plugin_registry import PluginRegistry
from vnstock.providers.dnse.plugin import DNSEProviderPlugin
from vnstock.providers.fmarket.plugin import FMarketProviderPlugin
from vnstock.providers.fmp.plugin import FMPProviderPlugin

# Lazily imported at registration time to avoid circular imports and
# unnecessary import cost when only the UI layer is used.
from vnstock.providers.kbs.plugin import KBSProviderPlugin
from vnstock.providers.msn.plugin import MSNProviderPlugin
from vnstock.providers.tcbs.plugin import TCBSProviderPlugin
from vnstock.providers.vci.plugin import VCIProviderPlugin

# ---------------------------------------------------------------------------
# Global plugin registry — one instance shared across the package.
# ---------------------------------------------------------------------------
REGISTRY: PluginRegistry = PluginRegistry()

REGISTRY.register(KBSProviderPlugin())
REGISTRY.register(VCIProviderPlugin())
REGISTRY.register(DNSEProviderPlugin())
REGISTRY.register(TCBSProviderPlugin())
REGISTRY.register(FMarketProviderPlugin())
REGISTRY.register(MSNProviderPlugin())
REGISTRY.register(FMPProviderPlugin())

__all__ = [
    "REGISTRY",
    "KBSProviderPlugin",
    "VCIProviderPlugin",
    "DNSEProviderPlugin",
    "TCBSProviderPlugin",
    "FMarketProviderPlugin",
    "MSNProviderPlugin",
    "FMPProviderPlugin",
]
