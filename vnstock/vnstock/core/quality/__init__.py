"""Data quality layer for vnstock.

Provides schema validation, freshness checks, and structured
validation reports for market data DataFrames.

Usage::

    from vnstock.core.quality import validate_dataframe

    report = validate_dataframe(
        df,
        dataset_type="ohlcv",
        provider="DNSE",
        symbol="FPT",
        interval="1D",
    )
"""

from vnstock.core.quality.exceptions import (
    DataQualityError,
    FreshnessError,
    SchemaValidationError,
    VnstockQualityError,
)
from vnstock.core.quality.models import QualityIssue, ValidationReport
from vnstock.core.quality.registry import validate_dataframe

__all__ = [
    "QualityIssue",
    "ValidationReport",
    "VnstockQualityError",
    "DataQualityError",
    "SchemaValidationError",
    "FreshnessError",
    "validate_dataframe",
]
