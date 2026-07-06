"""
vnstock/core/runtime — Plugin Runtime package.

Provides the high-level execution path:

    DatasetRequest → PluginRuntime → PluginRegistry/PluginRouter → ProviderPlugin
                   → DataResult → DataFrame

Public API::

    from vnstock.core.runtime import PluginRuntime, DatasetRequest, default_runtime

    rt = default_runtime()
    df = rt.fetch("equity.ohlcv", {"symbol": "FPT", "start": "2024-01-01"})
    # Or get a DataResult:
    result = rt.fetch("equity.ohlcv", {"symbol": "FPT"}, return_result=True)
"""

from __future__ import annotations

from vnstock.core.runtime.bootstrap import default_plugin_registry
from vnstock.core.runtime.plugin_runtime import PluginRuntime
from vnstock.core.runtime.request import DatasetRequest

__all__ = [
    "PluginRuntime",
    "DatasetRequest",
    "default_plugin_registry",
    "default_runtime",
]

_default_runtime: PluginRuntime | None = None


def default_runtime() -> PluginRuntime:
    """Return the module-level singleton PluginRuntime.

    The first call creates the runtime using :func:`default_plugin_registry`.
    Subsequent calls return the same instance.

    Returns:
        The shared :class:`PluginRuntime` instance.
    """
    global _default_runtime
    if _default_runtime is None:
        registry = default_plugin_registry()
        _default_runtime = PluginRuntime(registry=registry)
    return _default_runtime
