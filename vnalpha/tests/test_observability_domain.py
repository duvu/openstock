"""Tests for domain-level observability logging (Section 10)."""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def isolated_run_ctx(tmp_path):
    from vnalpha.observability.context import RunContext, reset_run_context

    reset_run_context()
    ctx = RunContext(
        run_id="domain_test_run",
        surface="cli",
        actor="test",
        log_root=tmp_path,
    )
    yield ctx
    reset_run_context()


@pytest.fixture(autouse=True)
def reset_run_ctx():
    from vnalpha.observability.context import reset_run_context

    reset_run_context()
    yield
    reset_run_context()


class TestDomainLogging:
    def test_migration_start_success(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.domain import (
            log_migration_start,
            log_migration_success,
        )

        set_correlation_id()
        log_migration_start("warehouse", run_ctx=isolated_run_ctx)
        log_migration_success("warehouse", run_ctx=isolated_run_ctx)

        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        types = {r["event_type"] for r in records}
        assert "WAREHOUSE_MIGRATION_STARTED" in types
        assert "WAREHOUSE_MIGRATION_RUN" in types

    def test_migration_failure(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.domain import log_migration_failure

        set_correlation_id()
        try:
            raise RuntimeError("ddl error")
        except RuntimeError as exc:
            log_migration_failure("warehouse", exc=exc, run_ctx=isolated_run_ctx)

        audit_records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        err_records = [
            json.loads(line)
            for line in isolated_run_ctx.errors_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(
            r["event_type"] == "WAREHOUSE_MIGRATION_FAILED" for r in audit_records
        )
        assert any(r["error_type"] == "RuntimeError" for r in err_records)

    def test_sync_success(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.domain import log_sync_start, log_sync_success

        set_correlation_id()
        log_sync_start("symbols", run_ctx=isolated_run_ctx)
        log_sync_success("symbols", row_count=42, run_ctx=isolated_run_ctx)

        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        types = {r["event_type"] for r in records}
        assert "SYNC_STARTED" in types
        assert "SYNC_COMPLETED" in types

    def test_sync_failure(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.domain import log_sync_failure

        set_correlation_id()
        try:
            raise ConnectionError("timeout")
        except ConnectionError as exc:
            log_sync_failure("ohlcv", exc=exc, run_ctx=isolated_run_ctx)

        err_records = [
            json.loads(line)
            for line in isolated_run_ctx.errors_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(r["error_type"] == "ConnectionError" for r in err_records)

    def test_feature_build_success(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.domain import log_feature_build_success

        set_correlation_id()
        log_feature_build_success(
            "2026-07-08", built=30, skipped=2, run_ctx=isolated_run_ctx
        )

        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(r["event_type"] == "FEATURE_BUILD_COMPLETE" for r in records)

    def test_feature_build_failure(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.domain import log_feature_build_failure

        set_correlation_id()
        try:
            raise ValueError("bad data")
        except ValueError as exc:
            log_feature_build_failure("2026-07-08", exc=exc, run_ctx=isolated_run_ctx)

        audit_records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(r["event_type"] == "FEATURE_BUILD_FAILED" for r in audit_records)

    def test_scoring_success(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.domain import log_scoring_success

        set_correlation_id()
        log_scoring_success("2026-07-08", scored=30, saved=15, run_ctx=isolated_run_ctx)

        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(r["event_type"] == "SCORING_COMPLETE" for r in records)

    def test_scoring_failure(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.domain import log_scoring_failure

        set_correlation_id()
        try:
            raise TypeError("bad score input")
        except TypeError as exc:
            log_scoring_failure("2026-07-08", exc=exc, run_ctx=isolated_run_ctx)

        err_records = [
            json.loads(line)
            for line in isolated_run_ctx.errors_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(r["error_type"] == "TypeError" for r in err_records)

    def test_outcome_eval_success(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.domain import log_outcome_eval_success

        set_correlation_id()
        log_outcome_eval_success(
            "2026-07-08", evaluated=10, persisted=10, run_ctx=isolated_run_ctx
        )

        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(r["event_type"] == "OUTCOME_EVALUATION_COMPLETE" for r in records)

    def test_outcome_eval_failure(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.domain import log_outcome_eval_failure

        set_correlation_id()
        try:
            raise RuntimeError("evaluation failed")
        except RuntimeError as exc:
            log_outcome_eval_failure("2026-07-08", exc=exc, run_ctx=isolated_run_ctx)

        err_records = [
            json.loads(line)
            for line in isolated_run_ctx.errors_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(r["error_type"] == "RuntimeError" for r in err_records)

    def test_data_quality_warning(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.domain import log_data_quality_warning

        set_correlation_id()
        log_data_quality_warning(
            "Missing benchmark data for VNINDEX",
            module="vnalpha.features",
            run_ctx=isolated_run_ctx,
        )

        err_records = [
            json.loads(line)
            for line in isolated_run_ctx.errors_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(r["event_type"] == "DATA_QUALITY_WARNING" for r in err_records)
        assert any(r["level"] == "WARNING" for r in err_records)
