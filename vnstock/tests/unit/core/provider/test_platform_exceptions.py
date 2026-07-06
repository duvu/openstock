"""
Unit tests for platform-level exceptions.
"""

from vnstock.core.provider.exceptions import (
    DatasetContractError,
    ProviderFetchError,
    ProviderNotFoundError,
    UnsupportedDatasetError,
    UnsupportedDatasetForProviderError,
    VnstockPlatformError,
)


class TestExceptionHierarchy:
    """Task 56-62: Platform exception hierarchy."""

    def test_base_exception(self):
        err = VnstockPlatformError("base error")
        assert isinstance(err, Exception)
        assert str(err) == "base error"

    def test_dataset_contract_error_inherits_base(self):
        err = DatasetContractError("equity.ohlcv")
        assert isinstance(err, VnstockPlatformError)
        assert "equity.ohlcv" in str(err)

    def test_dataset_contract_error_stores_dataset(self):
        err = DatasetContractError("fund.nav", "missing required column")
        assert err.dataset == "fund.nav"
        assert "missing required column" in str(err)

    def test_provider_not_found_inherits_base(self):
        err = ProviderNotFoundError("UNKNOWN")
        assert isinstance(err, VnstockPlatformError)
        assert "UNKNOWN" in str(err)

    def test_provider_not_found_stores_name(self):
        err = ProviderNotFoundError("BOGUS")
        assert err.provider_name == "BOGUS"

    def test_unsupported_dataset_error(self):
        err = UnsupportedDatasetError("foreign_flow.daily")
        assert isinstance(err, VnstockPlatformError)
        assert "foreign_flow.daily" in str(err)
        assert err.dataset == "foreign_flow.daily"

    def test_unsupported_dataset_for_provider_error(self):
        err = UnsupportedDatasetForProviderError("KBS", "fund.nav")
        assert isinstance(err, VnstockPlatformError)
        assert "KBS" in str(err)
        assert "fund.nav" in str(err)
        assert err.provider_name == "KBS"
        assert err.dataset == "fund.nav"

    def test_provider_fetch_error(self):
        cause = RuntimeError("timeout")
        err = ProviderFetchError("VCI", "equity.ohlcv", cause=cause)
        assert isinstance(err, VnstockPlatformError)
        assert "VCI" in str(err)
        assert "equity.ohlcv" in str(err)
        assert err.cause is cause

    def test_provider_fetch_error_without_cause(self):
        err = ProviderFetchError("KBS", "equity.quote")
        assert err.cause is None
        assert "KBS" in str(err)
