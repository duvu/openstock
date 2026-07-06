"""Tests for vnstock.core.quality.models."""

import json

import pytest

from vnstock.core.quality.models import QualityIssue, ValidationReport


class TestQualityIssue:
    def test_minimal_construction(self):
        issue = QualityIssue(
            code="SCHEMA_EMPTY_DATAFRAME", severity="error", message="Empty"
        )
        assert issue.code == "SCHEMA_EMPTY_DATAFRAME"
        assert issue.severity == "error"
        assert issue.message == "Empty"
        assert issue.column is None
        assert issue.row_index is None
        assert issue.value is None
        assert issue.context == {}

    def test_full_construction(self):
        issue = QualityIssue(
            code="NUMERIC_NEGATIVE_PRICE",
            severity="error",
            message="Negative price",
            column="close",
            row_index=5,
            value=-100,
            context={"symbol": "FPT"},
        )
        assert issue.column == "close"
        assert issue.row_index == 5
        assert issue.value == -100
        assert issue.context == {"symbol": "FPT"}

    def test_to_dict(self):
        issue = QualityIssue(code="X", severity="warning", message="m")
        d = issue.to_dict()
        assert d["code"] == "X"
        assert d["severity"] == "warning"
        assert isinstance(d, dict)

    def test_to_json(self):
        issue = QualityIssue(code="X", severity="info", message="m")
        raw = issue.to_json()
        parsed = json.loads(raw)
        assert parsed["code"] == "X"


class TestValidationReport:
    def _make_report(self, errors=None, warnings=None, infos=None):
        return ValidationReport(
            valid=not errors,
            dataset_type="ohlcv",
            provider="DNSE",
            symbol="FPT",
            interval="1D",
            row_count=10,
            latest_time="2026-07-01",
            freshness_status="fresh",
            errors=errors or [],
            warnings=warnings or [],
            infos=infos or [],
        )

    def test_valid_report(self):
        r = self._make_report()
        assert r.valid is True
        assert r.severity == "info"
        assert r.all_issues == []

    def test_severity_error(self):
        err = QualityIssue(
            code="SCHEMA_MISSING_COLUMN", severity="error", message="Missing col"
        )
        r = self._make_report(errors=[err])
        assert r.severity == "error"
        assert r.valid is False

    def test_severity_warning_no_error(self):
        warn = QualityIssue(code="FRESHNESS_STALE", severity="warning", message="Stale")
        r = self._make_report(warnings=[warn])
        assert r.severity == "warning"
        assert r.valid is True  # no errors → valid=True as constructed

    def test_severity_info_only(self):
        info = QualityIssue(
            code="TRADE_SYNTHETIC_ID", severity="info", message="Synthetic id"
        )
        r = self._make_report(infos=[info])
        assert r.severity == "info"

    def test_all_issues_concatenation(self):
        err = QualityIssue(code="E", severity="error", message="e")
        warn = QualityIssue(code="W", severity="warning", message="w")
        info = QualityIssue(code="I", severity="info", message="i")
        r = self._make_report(errors=[err], warnings=[warn], infos=[info])
        assert len(r.all_issues) == 3

    def test_to_dict_structure(self):
        r = self._make_report()
        d = r.to_dict()
        assert "valid" in d
        assert "errors" in d
        assert "warnings" in d
        assert "infos" in d
        assert "severity" in d
        assert isinstance(d["errors"], list)

    def test_to_json_roundtrip(self):
        r = self._make_report()
        raw = r.to_json()
        parsed = json.loads(raw)
        assert parsed["dataset_type"] == "ohlcv"
        assert parsed["provider"] == "DNSE"

    def test_to_dict_includes_issues(self):
        err = QualityIssue(
            code="SCHEMA_EMPTY_DATAFRAME", severity="error", message="Empty"
        )
        r = self._make_report(errors=[err])
        d = r.to_dict()
        assert len(d["errors"]) == 1
        assert d["errors"][0]["code"] == "SCHEMA_EMPTY_DATAFRAME"

    @pytest.mark.parametrize(
        "n_errors,n_warnings,expected_severity",
        [
            (0, 0, "info"),
            (0, 1, "warning"),
            (1, 0, "error"),
            (1, 1, "error"),
        ],
    )
    def test_severity_aggregation_parametrized(
        self, n_errors, n_warnings, expected_severity
    ):
        errors = [QualityIssue(code="E", severity="error", message="e")] * n_errors
        warnings = [
            QualityIssue(code="W", severity="warning", message="w")
        ] * n_warnings
        r = self._make_report(errors=errors, warnings=warnings)
        assert r.severity == expected_severity
