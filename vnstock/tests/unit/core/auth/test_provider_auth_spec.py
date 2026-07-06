"""Tests for provider auth_spec declarations (task 37)."""

from __future__ import annotations

import pytest

from vnstock.core.auth.spec import AuthSpec
from vnstock.core.auth.types import AuthType
from vnstock.providers.dnse.plugin import DNSEProviderPlugin
from vnstock.providers.fmarket.plugin import FMarketProviderPlugin
from vnstock.providers.fmp.plugin import FMPProviderPlugin
from vnstock.providers.kbs.plugin import KBSProviderPlugin
from vnstock.providers.msn.plugin import MSNProviderPlugin
from vnstock.providers.tcbs.plugin import TCBSProviderPlugin
from vnstock.providers.vci.plugin import VCIProviderPlugin

# ---------------------------------------------------------------------------
# Public provider — no auth
# ---------------------------------------------------------------------------


class TestPublicProviderAuthSpec:
    """Public providers should return no-auth spec."""

    @pytest.mark.parametrize(
        "plugin_cls",
        [
            KBSProviderPlugin,
            VCIProviderPlugin,
            DNSEProviderPlugin,
            MSNProviderPlugin,
            FMarketProviderPlugin,
        ],
    )
    def test_no_auth_for_public_provider(self, plugin_cls):
        plugin = plugin_cls()
        spec = plugin.auth_spec("equity.ohlcv")
        assert isinstance(spec, AuthSpec)
        assert spec.auth_type == AuthType.NONE
        assert spec.required is False
        assert spec.experimental is False
        assert spec.explicit_only is False

    @pytest.mark.parametrize(
        "plugin_cls",
        [
            KBSProviderPlugin,
            VCIProviderPlugin,
            DNSEProviderPlugin,
            MSNProviderPlugin,
            FMarketProviderPlugin,
        ],
    )
    def test_no_auth_for_any_dataset(self, plugin_cls):
        plugin = plugin_cls()
        for dataset in ["equity.ohlcv", "equity.quote", "fund.nav"]:
            spec = plugin.auth_spec(dataset)
            assert spec.auth_type == AuthType.NONE


# ---------------------------------------------------------------------------
# FMP — API key (non-interactive)
# ---------------------------------------------------------------------------


class TestFMPAuthSpec:
    def test_fmp_requires_api_key(self):
        plugin = FMPProviderPlugin()
        spec = plugin.auth_spec("equity.ohlcv")
        assert spec.auth_type == AuthType.API_KEY
        assert spec.required is True
        assert spec.experimental is False

    def test_fmp_not_explicit_only(self):
        """FMP can be included in auto-routing (API key is static config)."""
        plugin = FMPProviderPlugin()
        spec = plugin.auth_spec("equity.ohlcv")
        assert spec.explicit_only is False


# ---------------------------------------------------------------------------
# TCBS — experimental, explicit-only, interactive login
# ---------------------------------------------------------------------------


class TestTCBSAuthSpec:
    def test_tcbs_is_interactive(self):
        plugin = TCBSProviderPlugin()
        spec = plugin.auth_spec("equity.ohlcv")
        assert spec.auth_type == AuthType.INTERACTIVE

    def test_tcbs_is_experimental(self):
        plugin = TCBSProviderPlugin()
        spec = plugin.auth_spec("equity.ohlcv")
        assert spec.experimental is True

    def test_tcbs_is_explicit_only(self):
        """TCBS should not be selected in auto-routing."""
        plugin = TCBSProviderPlugin()
        spec = plugin.auth_spec("equity.ohlcv")
        assert spec.explicit_only is True

    def test_tcbs_is_required(self):
        plugin = TCBSProviderPlugin()
        spec = plugin.auth_spec("equity.ohlcv")
        assert spec.required is True

    def test_tcbs_scopes_are_data_read_only(self):
        """TCBS scopes must not include account/order/portfolio."""
        plugin = TCBSProviderPlugin()
        spec = plugin.auth_spec("equity.ohlcv")
        forbidden_scopes = {"account", "order", "portfolio", "transfer", "margin"}
        for scope in spec.scopes:
            assert scope not in forbidden_scopes, f"Forbidden scope found: {scope}"

    def test_tcbs_has_data_read_scopes(self):
        plugin = TCBSProviderPlugin()
        spec = plugin.auth_spec("equity.ohlcv")
        assert "equity.ohlcv" in spec.scopes


# ---------------------------------------------------------------------------
# auth_spec returns AuthSpec instance
# ---------------------------------------------------------------------------


class TestAuthSpecReturnType:
    @pytest.mark.parametrize(
        "plugin_cls",
        [
            KBSProviderPlugin,
            VCIProviderPlugin,
            DNSEProviderPlugin,
            MSNProviderPlugin,
            FMPProviderPlugin,
            TCBSProviderPlugin,
            FMarketProviderPlugin,
        ],
    )
    def test_auth_spec_returns_auth_spec(self, plugin_cls):
        plugin = plugin_cls()
        spec = plugin.auth_spec("equity.ohlcv")
        assert isinstance(spec, AuthSpec)
