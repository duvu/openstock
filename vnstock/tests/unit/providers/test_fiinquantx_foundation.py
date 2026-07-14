from __future__ import annotations

import importlib.util

import pytest

from vnstock.core.provider.exceptions import ProviderDisabledError
from vnstock.core.provider.plugin import ProviderPlugin
from vnstock.core.runtime.bootstrap import default_plugin_registry


def test_default_registry_constructs_without_fiinquantx() -> None:
    registry = default_plugin_registry()

    assert "FIINQUANTX" in registry.names()
    assert importlib.util.find_spec("fiinquantx") is None


def test_fiinquantx_is_fail_closed_until_runtime_evidence() -> None:
    registry = default_plugin_registry()
    plugin = registry.get("FIINQUANTX")

    capabilities = plugin.capabilities()

    assert capabilities
    assert all(not item["supported"] for item in capabilities.values())
    assert all(item["status"] == "unsupported" for item in capabilities.values())
    with pytest.raises(ProviderDisabledError):
        plugin.fetch("equity.ohlcv", {"symbol": "FPT"})


def test_fiinquantx_conforms_to_provider_plugin() -> None:
    plugin = default_plugin_registry().get("FIINQUANTX")

    assert isinstance(plugin, ProviderPlugin)


def test_fiinquantx_does_not_expose_forbidden_sdk_surfaces() -> None:
    from vnstock.providers.fiinquantx.policy import FORBIDDEN_MEMBER_NAMES

    assert "order" in FORBIDDEN_MEMBER_NAMES
    assert "positions" in FORBIDDEN_MEMBER_NAMES
    assert "account" in FORBIDDEN_MEMBER_NAMES
    assert "Fetch_Trading_Data" not in FORBIDDEN_MEMBER_NAMES
