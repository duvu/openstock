"""Unit tests for vnstock.core.provider.models."""

import json
from datetime import datetime

import pytest

from vnstock.core.provider.models import (
    ProviderCapability,
    ProviderComparisonReport,
    ProviderHealth,
    ProviderIssue,
)


class TestProviderCapability:
    def test_basic_construction(self):
        cap = ProviderCapability(
            provider="DNSE",
            dataset_type="ohlcv",
            asset_class="equity",
            method="history",
            intervals=["1D", "1W", "1M"],
            supports_history=True,
        )
        assert cap.provider == "DNSE"
        assert cap.dataset_type == "ohlcv"
        assert cap.asset_class == "equity"
        assert cap.method == "history"
        assert "1D" in cap.intervals
        assert cap.supports_history is True
        assert cap.requires_auth is False

    def test_frozen_immutability(self):
        cap = ProviderCapability(
            provider="KBS",
            dataset_type="ohlcv",
            asset_class="equity",
            method="history",
            intervals=["1D"],
        )
        with pytest.raises((AttributeError, TypeError)):
            cap.provider = "VCI"  # type: ignore[misc]

    def test_to_dict_serialization(self):
        cap = ProviderCapability(
            provider="VCI",
            dataset_type="price_board",
            asset_class="equity",
            method="price_board",
            intervals=[],
            supports_live_snapshot=True,
            notes="VCI price board",
        )
        d = cap.to_dict()
        assert d["provider"] == "VCI"
        assert d["dataset_type"] == "price_board"
        assert d["supports_live_snapshot"] is True
        assert d["notes"] == "VCI price board"

    def test_to_json_serialization(self):
        cap = ProviderCapability(
            provider="DNSE",
            dataset_type="intraday_trades",
            asset_class="equity",
            method="intraday",
            intervals=[],
            supports_intraday=True,
        )
        raw = cap.to_json()
        parsed = json.loads(raw)
        assert parsed["provider"] == "DNSE"
        assert parsed["supports_intraday"] is True


class TestProviderIssue:
    def test_basic_construction(self):
        issue = ProviderIssue(
            code="SCHEMA_DRIFT_MAJOR",
            severity="error",
            provider="KBS",
            capability="ohlcv/equity",
            message="Required field 'volume' missing from raw response",
        )
        assert issue.code == "SCHEMA_DRIFT_MAJOR"
        assert issue.severity == "error"
        assert issue.provider == "KBS"

    def test_to_dict(self):
        issue = ProviderIssue(
            code="SCHEMA_DRIFT_MINOR",
            severity="warning",
            provider="VCI",
            capability="ohlcv/equity",
            message="Optional field added",
            context={"field": "extra_col"},
        )
        d = issue.to_dict()
        assert d["code"] == "SCHEMA_DRIFT_MINOR"
        assert d["context"] == {"field": "extra_col"}

    def test_to_json(self):
        issue = ProviderIssue(
            code="STALE_DATA",
            severity="warning",
            provider="DNSE",
            capability="price_board/equity",
            message="Data is stale",
        )
        raw = issue.to_json()
        parsed = json.loads(raw)
        assert parsed["severity"] == "warning"


class TestProviderHealth:
    def test_basic_construction(self):
        health = ProviderHealth(
            provider="DNSE",
            status="healthy",
            checked_at=datetime(2026, 7, 2, 9, 0, 0),
        )
        assert health.provider == "DNSE"
        assert health.status == "healthy"
        assert health.schema_status == "unknown"
        assert health.freshness_status == "unknown"
        assert health.issues == []

    def test_to_dict_includes_iso_timestamp(self):
        ts = datetime(2026, 7, 2, 9, 0, 0)
        health = ProviderHealth(
            provider="KBS",
            status="degraded",
            checked_at=ts,
            capabilities_checked=["ohlcv/equity"],
            latency_ms=450.0,
        )
        d = health.to_dict()
        assert d["checked_at"] == "2026-07-02T09:00:00"
        assert d["latency_ms"] == 450.0

    def test_to_json(self):
        ts = datetime(2026, 7, 2)
        health = ProviderHealth(
            provider="VCI",
            status="failing",
            checked_at=ts,
            schema_status="drifted",
            issues=[
                ProviderIssue(
                    code="SCHEMA_DRIFT_MAJOR",
                    severity="error",
                    provider="VCI",
                    capability="ohlcv/equity",
                    message="Missing column",
                )
            ],
        )
        raw = health.to_json()
        parsed = json.loads(raw)
        assert parsed["status"] == "failing"
        assert parsed["schema_status"] == "drifted"
        assert len(parsed["issues"]) == 1

    def test_unknown_status_defaults(self):
        health = ProviderHealth(
            provider="MSN",
            status="unknown",
            checked_at=datetime(2026, 1, 1),
        )
        assert health.error_rate is None
        assert health.latency_ms is None


class TestProviderComparisonReport:
    def test_basic_construction(self):
        report = ProviderComparisonReport(
            dataset_type="ohlcv",
            symbol="FPT",
            providers=["KBS", "VCI", "DNSE"],
            comparable=True,
            base_provider="KBS",
        )
        assert report.symbol == "FPT"
        assert report.comparable is True
        assert report.base_provider == "KBS"
        assert report.row_count_by_provider == {}

    def test_to_dict_full(self):
        report = ProviderComparisonReport(
            dataset_type="ohlcv",
            symbol="VCB",
            providers=["KBS", "VCI"],
            comparable=True,
            base_provider="KBS",
            row_count_by_provider={"KBS": 100, "VCI": 98},
            missing_dates_by_provider={"VCI": ["2026-06-30"]},
            price_diff_summary={"max_pct": 0.005, "mean_pct": 0.001},
            volume_diff_summary={"max_pct": 0.03},
            interval="1D",
            start="2026-01-01",
            end="2026-07-02",
        )
        d = report.to_dict()
        assert d["row_count_by_provider"]["KBS"] == 100
        assert d["missing_dates_by_provider"]["VCI"] == ["2026-06-30"]
        assert d["interval"] == "1D"

    def test_to_json(self):
        report = ProviderComparisonReport(
            dataset_type="price_board",
            symbol="ACB",
            providers=["DNSE"],
            comparable=False,
            base_provider="DNSE",
            issues=["Only one provider available"],
        )
        raw = report.to_json()
        parsed = json.loads(raw)
        assert parsed["comparable"] is False
        assert parsed["issues"] == ["Only one provider available"]
