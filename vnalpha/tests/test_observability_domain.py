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
