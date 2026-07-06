"""Typed exceptions for the data quality layer.

Exception hierarchy::

    VnstockQualityError
    └── DataQualityError
        ├── SchemaValidationError
        └── FreshnessError
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnstock.core.quality.models import ValidationReport


class VnstockQualityError(Exception):
    """Base class for all data quality exceptions in vnstock."""


class DataQualityError(VnstockQualityError):
    """Raised when data quality validation fails in strict mode.

    Attributes:
        report: The :class:`~vnstock.core.quality.models.ValidationReport`
            produced by the failed validation run.
    """

    def __init__(self, report: "ValidationReport") -> None:
        self.report = report
        super().__init__(f"Data quality validation failed: {report.severity}")


class SchemaValidationError(DataQualityError):
    """Raised when the DataFrame schema does not match the expected contract.

    Typical codes: ``SCHEMA_MISSING_COLUMN``, ``SCHEMA_EMPTY_DATAFRAME``,
    ``SCHEMA_INVALID_DTYPE``.
    """


class FreshnessError(DataQualityError):
    """Raised when the DataFrame data is too stale for the configured threshold.

    Typical codes: ``FRESHNESS_STALE``, ``FRESHNESS_LATEST_TIME_MISSING``.
    """
