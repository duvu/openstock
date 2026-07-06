"""Unit tests for vnstock.core.provider.capabilities."""

import pytest

from vnstock.core.provider.capabilities import CAPABILITIES, query_capabilities


class TestCapabilitiesRegistry:
    def test_capabilities_list_not_empty(self):
        assert len(CAPABILITIES) > 0

    def test_all_known_providers_represented(self):
        providers = {c.provider for c in CAPABILITIES}
        assert "KBS" in providers
        assert "VCI" in providers
        assert "DNSE" in providers
        assert "MSN" in providers
        assert "FMP" in providers
        assert "FMARKET" in providers
        assert "TCBS" in providers


class TestQueryCapabilities:
    def test_query_by_provider(self):
        caps = query_capabilities(provider="KBS")
        assert len(caps) > 0
        assert all(c.provider == "KBS" for c in caps)

    def test_query_by_provider_case_insensitive(self):
        caps_upper = query_capabilities(provider="VCI")
        caps_lower = query_capabilities(provider="vci")
        assert len(caps_upper) == len(caps_lower)

    def test_query_by_dataset_type_ohlcv(self):
        caps = query_capabilities(dataset_type="ohlcv")
        assert len(caps) > 0
        assert all(c.dataset_type == "ohlcv" for c in caps)

    def test_query_by_dataset_type_price_board(self):
        caps = query_capabilities(dataset_type="price_board")
        assert len(caps) > 0
        assert all(c.dataset_type == "price_board" for c in caps)

    def test_query_by_asset_class(self):
        caps = query_capabilities(asset_class="equity")
        assert len(caps) > 0
        assert all(c.asset_class == "equity" for c in caps)

    def test_query_by_interval_1D(self):
        caps = query_capabilities(interval="1D")
        assert len(caps) > 0
        assert all("1D" in c.intervals for c in caps)

    def test_query_by_interval_intraday(self):
        caps = query_capabilities(interval="1m")
        assert len(caps) > 0
        assert all("1m" in c.intervals for c in caps)

    def test_combined_query_ohlcv_equity(self):
        caps = query_capabilities(dataset_type="ohlcv", asset_class="equity")
        assert len(caps) > 0
        providers = {c.provider for c in caps}
        # KBS, VCI, DNSE, TCBS all support equity OHLCV
        assert providers >= {"KBS", "VCI", "DNSE", "TCBS"}

    def test_combined_query_provider_and_dataset(self):
        caps = query_capabilities(provider="DNSE", dataset_type="price_board")
        assert len(caps) == 1
        assert caps[0].provider == "DNSE"
        assert caps[0].dataset_type == "price_board"

    def test_unsupported_capability_returns_empty_list(self):
        # MSN doesn't support intraday
        caps = query_capabilities(provider="MSN", dataset_type="intraday_trades")
        assert caps == []

    def test_unsupported_provider_returns_empty_list(self):
        caps = query_capabilities(provider="NONEXISTENT_PROVIDER")
        assert caps == []

    def test_unsupported_dataset_type_returns_empty_list(self):
        caps = query_capabilities(dataset_type="nonexistent_type")
        assert caps == []

    def test_no_filters_returns_all(self):
        caps = query_capabilities()
        assert len(caps) == len(CAPABILITIES)

    def test_fmp_requires_auth(self):
        caps = query_capabilities(provider="FMP")
        assert all(c.requires_auth for c in caps)

    def test_dnse_intraday_not_live_testable(self):
        caps = query_capabilities(provider="DNSE", dataset_type="intraday_trades")
        assert len(caps) == 1
        assert caps[0].is_live_testable is False
        assert caps[0].requires_auth is True

    def test_kbs_ohlcv_supports_history(self):
        caps = query_capabilities(
            provider="KBS", dataset_type="ohlcv", asset_class="equity"
        )
        assert len(caps) == 1
        assert caps[0].supports_history is True

    def test_price_board_providers_support_batch(self):
        caps = query_capabilities(dataset_type="price_board")
        assert all(c.supports_batch for c in caps)

    @pytest.mark.parametrize("provider", ["KBS", "VCI", "DNSE", "TCBS"])
    def test_major_providers_have_ohlcv_equity(self, provider: str):
        caps = query_capabilities(
            provider=provider, dataset_type="ohlcv", asset_class="equity"
        )
        assert len(caps) >= 1, f"{provider} should have ohlcv/equity capability"

    def test_tcbs_ohlcv_requires_auth(self):
        """TCBS OHLCV requires Bearer token auth (APIs moved to apiextaws in 2025)."""
        caps = query_capabilities(provider="TCBS", dataset_type="ohlcv")
        assert len(caps) >= 1
        assert all(c.requires_auth for c in caps)

    def test_tcbs_screener_is_experimental(self):
        caps = query_capabilities(provider="TCBS", dataset_type="screener")
        assert len(caps) >= 1
        assert all("experimental" in (c.notes or "").lower() for c in caps)
