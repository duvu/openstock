"""Tests for vnstock.service.dataset_mapper."""

from __future__ import annotations

import warnings

import pytest

from vnstock.service.dataset_mapper import (
    MapperError,
    extract_runtime_params,
    path_to_dataset,
)


class TestPathToDataset:
    """Test canonical path mapping."""

    # Canonical paths
    @pytest.mark.parametrize(
        "path, expected",
        [
            ("/v1/equity/ohlcv", "equity.ohlcv"),
            ("/v1/equity/quote", "equity.quote"),
            ("/v1/equity/intraday-trades", "equity.intraday_trades"),
            ("/v1/index/ohlcv", "index.ohlcv"),
            ("/v1/reference/symbols", "reference.symbols"),
            ("/v1/company/info", "reference.company_info"),
            ("/v1/fundamental/balance-sheet", "fundamental.balance_sheet"),
            ("/v1/fundamental/income-statement", "fundamental.income_statement"),
            ("/v1/fundamental/cash-flow", "fundamental.cash_flow"),
            ("/v1/fundamental/financial-ratio", "fundamental.financial_ratio"),
            ("/v1/fund/nav", "fund.nav"),
            ("/v1/fund/holdings", "fund.holdings"),
        ],
    )
    def test_canonical_paths(self, path, expected):
        assert path_to_dataset(path) == expected

    def test_trailing_slash_ignored(self):
        assert path_to_dataset("/v1/equity/ohlcv/") == "equity.ohlcv"

    def test_case_insensitive(self):
        assert path_to_dataset("/V1/EQUITY/OHLCV") == "equity.ohlcv"


class TestDeprecatedAliases:
    """Test deprecated alias paths emit warnings and still resolve."""

    def test_market_ohlcv_alias(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            dataset = path_to_dataset("/v1/market/ohlcv")
        assert dataset == "equity.ohlcv"
        assert any(issubclass(warning.category, DeprecationWarning) for warning in w)

    def test_reference_listing_alias(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            dataset = path_to_dataset("/v1/reference/listing")
        assert dataset == "reference.symbols"
        assert any(issubclass(warning.category, DeprecationWarning) for warning in w)


class TestUnknownPaths:
    """Unknown paths should raise MapperError."""

    def test_unknown_path_raises(self):
        with pytest.raises(MapperError):
            path_to_dataset("/v1/unknown/dataset")

    def test_empty_path_raises(self):
        with pytest.raises(MapperError):
            path_to_dataset("/v1/equity/")

    def test_partial_path_raises(self):
        with pytest.raises(MapperError):
            path_to_dataset("/v1/equity")

    def test_mapper_error_contains_path(self):
        bad_path = "/v1/nonexistent/thing"
        with pytest.raises(MapperError) as exc_info:
            path_to_dataset(bad_path)
        assert bad_path in str(exc_info.value)


class TestExtractRuntimeParams:
    """Test runtime control param extraction."""

    def test_empty_query(self):
        assert extract_runtime_params({}) == {}

    def test_source_extracted(self):
        result = extract_runtime_params({"source": ["KBS"], "symbol": ["FPT"]})
        assert result == {"source": "KBS"}

    def test_validate_extracted(self):
        result = extract_runtime_params({"validate": ["true"]})
        assert result == {"validate": "true"}

    def test_quality_mode_extracted(self):
        result = extract_runtime_params({"quality_mode": ["strict"]})
        assert result == {"quality_mode": "strict"}

    def test_non_runtime_params_excluded(self):
        result = extract_runtime_params({"symbol": ["FPT"], "start": ["2024-01-01"]})
        assert result == {}

    def test_all_runtime_params(self):
        query = {
            "source": ["VCI"],
            "validate": ["false"],
            "quality_mode": ["warn"],
            "symbol": ["FPT"],
        }
        result = extract_runtime_params(query)
        assert result == {"source": "VCI", "validate": "false", "quality_mode": "warn"}
