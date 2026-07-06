"""Service runtime dependency helper.

Provides a shared :class:`~vnstock.core.runtime.plugin_runtime.PluginRuntime`
for the local data service, with test-injection support.

Usage::

    from vnstock.service.runtime_dependency import get_runtime, override_runtime

    rt = get_runtime()
    result = rt.fetch("equity.ohlcv", {...}, return_result=True)

Test injection::

    from vnstock.service.runtime_dependency import override_runtime, reset_runtime

    override_runtime(fake_runtime)
    # ... run tests ...
    reset_runtime()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnstock.core.runtime.plugin_runtime import PluginRuntime

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_runtime: "PluginRuntime | None" = None


def get_runtime() -> "PluginRuntime":
    """Return the shared runtime singleton for the service.

    On first call the default plugin registry is initialised and a
    :class:`~vnstock.core.runtime.plugin_runtime.PluginRuntime` is created.
    Subsequent calls return the same instance.

    Returns:
        The shared :class:`~vnstock.core.runtime.plugin_runtime.PluginRuntime`.
    """
    global _runtime
    if _runtime is None:
        from vnstock.core.runtime import PluginRuntime, default_plugin_registry

        registry = default_plugin_registry()
        _runtime = PluginRuntime(registry=registry)
    return _runtime


def override_runtime(runtime: "PluginRuntime") -> None:
    """Replace the shared runtime with *runtime*.

    Intended for test injection only.  Call :func:`reset_runtime` to
    restore the default after tests.

    Args:
        runtime: A :class:`~vnstock.core.runtime.plugin_runtime.PluginRuntime`
            instance to use instead of the default.
    """
    global _runtime
    _runtime = runtime


def reset_runtime() -> None:
    """Clear the injected runtime and force re-initialisation on next call."""
    global _runtime
    _runtime = None
