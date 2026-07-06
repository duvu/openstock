"""
Backward compatibility tests.

These tests verify that the existing public Market/Reference/Fundamental API
continues to work unchanged after the Phase 1 plugin architecture introduction.

Tasks 63-67: confirm existing call paths remain stable.
"""

from unittest.mock import patch

import pandas as pd


class TestMarketImportUnchanged:
    """Task 63: Confirm Market import remains unchanged."""

    def test_market_importable_from_vnstock(self):
        """Market can be imported from vnstock top-level package."""
        from vnstock import Market  # noqa: F401

    def test_reference_importable(self):
        from vnstock import Reference  # noqa: F401

    def test_fundamental_importable(self):
        from vnstock import Fundamental  # noqa: F401

    def test_listing_importable(self):
        from vnstock import Listing  # noqa: F401


class TestEquityOHLCVPath:
    """Tasks 64-65: Confirm Market().equity.ohlcv() path is callable."""

    def test_market_equity_is_callable(self):
        """Task 64: Market().equity is callable and returns an object with ohlcv."""
        from vnstock import Market

        m = Market()
        eq = m.equity()
        assert callable(getattr(eq, "ohlcv", None))

    def test_equity_ohlcv_returns_dataframe_when_mocked(self):
        """Task 65: ohlcv() returns DataFrame (mocked provider)."""
        import pandas as pd

        from vnstock import Market
        from vnstock.ui._base import BaseUI

        mock_df = pd.DataFrame(
            {
                "time": pd.to_datetime(["2024-01-01"]),
                "open": [100.0],
                "high": [105.0],
                "low": [99.0],
                "close": [103.0],
                "volume": [100000.0],
            }
        )

        with patch.object(BaseUI, "_dispatch", return_value=mock_df):
            m = Market()
            eq = m.equity()
            df = eq.ohlcv(
                symbol="FPT",
                start="2024-01-01",
                end="2024-12-31",
                interval="1D",
            )
            assert isinstance(df, pd.DataFrame)


class TestQualityMetadataCompatibility:
    """Task 66: df.attrs['quality'] remains compatible."""

    def test_quality_attrs_key_accessible(self):
        """DataResult sets df.attrs['quality'] for backward compatibility."""
        from vnstock.core.result import DataResult

        df = pd.DataFrame({"symbol": ["FPT"]})
        report = {"checks": [{"name": "ohlcv_check", "status": "PASS"}]}
        result = DataResult(
            dataset="equity.ohlcv",
            provider="KBS",
            data=df,
            quality_status="PASS",
            quality_report=report,
        )
        out = result.to_dataframe()
        assert out.attrs.get("quality") == report

    def test_quality_status_attrs_key_accessible(self):
        """DataResult sets df.attrs['quality_status']."""
        from vnstock.core.result import DataResult

        df = pd.DataFrame({"symbol": ["FPT"]})
        result = DataResult(
            dataset="equity.ohlcv",
            provider="KBS",
            data=df,
            quality_status="PASS",
        )
        out = result.to_dataframe()
        assert out.attrs.get("quality_status") == "PASS"


class TestNewContractsDoNotBreakExistingImports:
    """Task 67: New contracts package does not shadow existing modules."""

    def test_core_contracts_importable(self):
        from vnstock.core.contracts import CONTRACT_REGISTRY  # noqa: F401

    def test_core_result_importable(self):
        from vnstock.core.result import DataResult  # noqa: F401

    def test_plugin_registry_importable(self):
        from vnstock.core.provider.plugin_registry import PluginRegistry  # noqa: F401

    def test_plugin_router_importable(self):
        from vnstock.core.provider.plugin_router import PluginRouter  # noqa: F401

    def test_platform_exceptions_importable(self):
        from vnstock.core.provider.exceptions import (  # noqa: F401
            DatasetContractError,
            ProviderFetchError,
            ProviderNotFoundError,
            UnsupportedDatasetError,
            UnsupportedDatasetForProviderError,
            VnstockPlatformError,
        )

    def test_existing_registry_not_affected(self):
        """The original ProviderRegistry in core/registry.py still works."""
        from vnstock.core.registry import ProviderRegistry

        # Original registry should have providers registered by explorer modules
        # At minimum the registry class is importable and has the original API
        assert hasattr(ProviderRegistry, "register")
        assert hasattr(ProviderRegistry, "get")
