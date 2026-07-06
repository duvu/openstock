"""Tests for vnstock.core.quality.exceptions."""

import pytest

from vnstock.core.quality.exceptions import (
    DataQualityError,
    FreshnessError,
    SchemaValidationError,
    VnstockQualityError,
)
from vnstock.core.quality.models import QualityIssue, ValidationReport


def _make_report(errors=None):
    return ValidationReport(
        valid=not errors,
        dataset_type="ohlcv",
        provider="DNSE",
        symbol="FPT",
        interval="1D",
        row_count=5,
        latest_time=None,
        freshness_status="unknown",
        errors=errors or [],
    )


class TestExceptionHierarchy:
    def test_data_quality_error_is_vnstock_quality_error(self):
        report = _make_report()
        exc = DataQualityError(report)
        assert isinstance(exc, VnstockQualityError)

    def test_schema_validation_error_is_data_quality_error(self):
        report = _make_report()
        exc = SchemaValidationError(report)
        assert isinstance(exc, DataQualityError)
        assert isinstance(exc, VnstockQualityError)

    def test_freshness_error_is_data_quality_error(self):
        report = _make_report()
        exc = FreshnessError(report)
        assert isinstance(exc, DataQualityError)
        assert isinstance(exc, VnstockQualityError)


class TestDataQualityError:
    def test_carries_report(self):
        err_issue = QualityIssue(
            code="SCHEMA_MISSING_COLUMN", severity="error", message="Missing 'close'"
        )
        report = _make_report(errors=[err_issue])
        exc = DataQualityError(report)
        assert exc.report is report

    def test_message_includes_severity(self):
        err_issue = QualityIssue(code="E", severity="error", message="e")
        report = _make_report(errors=[err_issue])
        exc = DataQualityError(report)
        assert "error" in str(exc)

    def test_strict_mode_raise_and_catch(self):
        report = _make_report(
            errors=[
                QualityIssue(
                    code="SCHEMA_EMPTY_DATAFRAME", severity="error", message="empty"
                )
            ]
        )
        with pytest.raises(DataQualityError) as exc_info:
            raise DataQualityError(report)
        assert exc_info.value.report.severity == "error"

    def test_schema_validation_error_raise_and_catch(self):
        report = _make_report(
            errors=[
                QualityIssue(
                    code="SCHEMA_MISSING_COLUMN", severity="error", message="x"
                )
            ]
        )
        with pytest.raises(SchemaValidationError):
            raise SchemaValidationError(report)

    def test_freshness_error_raise_and_catch(self):
        report = _make_report(
            errors=[
                QualityIssue(code="FRESHNESS_STALE", severity="error", message="stale")
            ]
        )
        with pytest.raises(FreshnessError):
            raise FreshnessError(report)

    def test_catch_as_vnstock_quality_error(self):
        report = _make_report()
        with pytest.raises(VnstockQualityError):
            raise FreshnessError(report)
