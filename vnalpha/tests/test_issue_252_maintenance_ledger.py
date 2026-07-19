"""Tests for issue #252: Maintenance run and stage ledger persistence."""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import pytest

from vnalpha.maintenance.ledger import (
    get_failed_maintenance_stages,
    get_latest_maintenance_run,
    get_maintenance_run_stages,
    persist_maintenance_run,
)
from vnalpha.maintenance.models import (
    DailyMaintenanceResult,
    MaintenanceRunStatus,
    MaintenanceStageResult,
    MaintenanceStageStatus,
)
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection, emit_observability=False)
    yield connection
    connection.close()


def test_persist_successful_maintenance_run(conn) -> None:
    # Given: a successful maintenance result
    result = DailyMaintenanceResult(
        status=MaintenanceRunStatus.SUCCESS,
        requested_date="2026-07-17",
        resolved_date="2026-07-17",
        correlation_id="test-corr-123",
        stages=(
            MaintenanceStageResult(
                name="incremental_ohlcv",
                status=MaintenanceStageStatus.SUCCESS,
                counts={"inserted": 100, "updated": 50},
            ),
            MaintenanceStageResult(
                name="features",
                status=MaintenanceStageStatus.SUCCESS,
                counts={"calculated": 150},
            ),
        ),
        requested_symbols=("VCB", "FPT", "HPG"),
        successful_symbols=("VCB", "FPT", "HPG"),
        failed_symbols=(),
        diagnostics_refs=(),
        mutated=True,
    )

    started_at = datetime(2026, 7, 17, 8, 0, 0, tzinfo=timezone.utc)
    completed_at = datetime(2026, 7, 17, 8, 5, 30, tzinfo=timezone.utc)

    # When: persisting the run
    run_id = persist_maintenance_run(
        conn,
        result,
        started_at=started_at,
        completed_at=completed_at,
        software_version="python-3.12.3",
        calendar_version="hnx-vnx-2026-1403-1517",
    )

    # Then: run is persisted with all fields
    assert run_id.startswith("maint_")
    latest = get_latest_maintenance_run(conn)
    assert latest is not None
    assert latest["run_id"] == run_id
    assert latest["correlation_id"] == "test-corr-123"
    assert latest["resolved_date"] == "2026-07-17"
    assert latest["status"] == "SUCCESS"
    assert latest["requested_symbol_count"] == 3
    assert latest["successful_symbol_count"] == 3
    assert latest["failed_symbol_count"] == 0
    assert latest["mutated"] is True
    assert latest["software_version"] == "python-3.12.3"
    assert latest["calendar_version"] == "hnx-vnx-2026-1403-1517"
    assert abs(latest["duration_seconds"] - 330.0) < 0.1


def test_persist_stages_in_order(conn) -> None:
    # Given: a result with multiple stages
    result = DailyMaintenanceResult(
        status=MaintenanceRunStatus.SUCCESS,
        requested_date=None,
        resolved_date="2026-07-17",
        correlation_id="stage-order-test",
        stages=(
            MaintenanceStageResult("stage_1", MaintenanceStageStatus.SUCCESS),
            MaintenanceStageResult("stage_2", MaintenanceStageStatus.SUCCESS),
            MaintenanceStageResult("stage_3", MaintenanceStageStatus.PARTIAL),
        ),
        requested_symbols=(),
        successful_symbols=(),
        failed_symbols=(),
        diagnostics_refs=(),
        mutated=False,
    )

    started_at = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    completed_at = datetime(2026, 7, 17, 8, 1, tzinfo=timezone.utc)

    # When: persisting
    run_id = persist_maintenance_run(
        conn,
        result,
        started_at=started_at,
        completed_at=completed_at,
        software_version="test",
    )

    # Then: stages are persisted in order
    stages = get_maintenance_run_stages(conn, run_id)
    assert len(stages) == 3
    assert stages[0]["stage_name"] == "stage_1"
    assert stages[0]["stage_order"] == 1
    assert stages[1]["stage_name"] == "stage_2"
    assert stages[1]["stage_order"] == 2
    assert stages[2]["stage_name"] == "stage_3"
    assert stages[2]["stage_order"] == 3


def test_persist_failed_run_with_diagnostics(conn) -> None:
    # Given: a failed run with diagnostics
    result = DailyMaintenanceResult(
        status=MaintenanceRunStatus.FAILED,
        requested_date="2026-07-17",
        resolved_date="2026-07-17",
        correlation_id="failed-run",
        stages=(
            MaintenanceStageResult(
                name="failed_stage",
                status=MaintenanceStageStatus.FAILED,
                failures=("Provider unavailable", "Network timeout"),
                diagnostics_refs=("diag-123", "diag-456"),
                remediation=("Check network", "Retry later"),
            ),
        ),
        requested_symbols=("VCB",),
        successful_symbols=(),
        failed_symbols=("VCB",),
        diagnostics_refs=("run-diag-789",),
        mutated=False,
    )

    started_at = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    completed_at = datetime(2026, 7, 17, 8, 0, 10, tzinfo=timezone.utc)

    # When: persisting
    run_id = persist_maintenance_run(
        conn,
        result,
        started_at=started_at,
        completed_at=completed_at,
        software_version="test",
    )

    # Then: failures and diagnostics are preserved
    latest = get_latest_maintenance_run(conn)
    assert latest["status"] == "FAILED"
    assert latest["failed_symbol_count"] == 1
    assert "run-diag-789" in latest["diagnostics_refs"]

    stages = get_maintenance_run_stages(conn, run_id)
    assert stages[0]["status"] == "FAILED"
    assert "Provider unavailable" in stages[0]["failures"]
    assert "Network timeout" in stages[0]["failures"]
    assert "diag-123" in stages[0]["diagnostics_refs"]
    assert "Check network" in stages[0]["remediation"]


def test_get_failed_stages_returns_recent_failures(conn) -> None:
    # Given: multiple runs with some failed stages
    for i in range(3):
        result = DailyMaintenanceResult(
            status=MaintenanceRunStatus.PARTIAL
            if i > 0
            else MaintenanceRunStatus.SUCCESS,
            requested_date="2026-07-17",
            resolved_date="2026-07-17",
            correlation_id=f"run-{i}",
            stages=(
                MaintenanceStageResult(
                    name=f"stage_{i}",
                    status=MaintenanceStageStatus.FAILED
                    if i > 0
                    else MaintenanceStageStatus.SUCCESS,
                    failures=(f"Error {i}",) if i > 0 else (),
                ),
            ),
            requested_symbols=(),
            successful_symbols=(),
            failed_symbols=(),
            diagnostics_refs=(),
            mutated=False,
        )
        persist_maintenance_run(
            conn,
            result,
            started_at=datetime(2026, 7, 17, 8, i, tzinfo=timezone.utc),
            completed_at=datetime(2026, 7, 17, 8, i, 30, tzinfo=timezone.utc),
            software_version="test",
        )

    # When: querying failed stages
    failed = get_failed_maintenance_stages(conn, limit=10)

    # Then: only failed/partial stages returned
    assert len(failed) == 2
    assert all(s["status"] in ("FAILED", "PARTIAL") for s in failed)
    assert failed[0]["stage_name"] == "stage_2"  # Most recent first
    assert failed[1]["stage_name"] == "stage_1"


def test_latest_run_is_most_recent_by_completion_time(conn) -> None:
    # Given: multiple runs at different times
    for i in range(3):
        result = DailyMaintenanceResult(
            status=MaintenanceRunStatus.SUCCESS,
            requested_date="2026-07-17",
            resolved_date="2026-07-17",
            correlation_id=f"time-test-{i}",
            stages=(),
            requested_symbols=(),
            successful_symbols=(),
            failed_symbols=(),
            diagnostics_refs=(),
            mutated=False,
        )
        persist_maintenance_run(
            conn,
            result,
            started_at=datetime(2026, 7, 17, 8, i, tzinfo=timezone.utc),
            completed_at=datetime(2026, 7, 17, 8, i, 1, tzinfo=timezone.utc),
            software_version="test",
        )

    # When: getting latest
    latest = get_latest_maintenance_run(conn)

    # Then: most recently completed run returned
    assert latest["correlation_id"] == "time-test-2"


def test_noop_run_is_persisted(conn) -> None:
    # Given: a NOOP run (non-trading day)
    result = DailyMaintenanceResult(
        status=MaintenanceRunStatus.NOOP,
        requested_date="2026-07-19",  # Sunday
        resolved_date="2026-07-19",
        correlation_id="noop-test",
        stages=(
            MaintenanceStageResult("resolve_session", MaintenanceStageStatus.SKIPPED),
        ),
        requested_symbols=(),
        successful_symbols=(),
        failed_symbols=(),
        diagnostics_refs=(),
        mutated=False,
    )

    started_at = datetime(2026, 7, 19, 8, 0, tzinfo=timezone.utc)
    completed_at = datetime(2026, 7, 19, 8, 0, 1, tzinfo=timezone.utc)

    # When: persisting
    _ = persist_maintenance_run(
        conn,
        result,
        started_at=started_at,
        completed_at=completed_at,
        software_version="test",
    )

    # Then: NOOP status preserved
    latest = get_latest_maintenance_run(conn)
    assert latest["status"] == "NOOP"
    assert latest["mutated"] is False


def test_stage_counts_and_warnings_are_json_serialized(conn) -> None:
    # Given: a stage with complex counts and warnings
    result = DailyMaintenanceResult(
        status=MaintenanceRunStatus.SUCCESS,
        requested_date="2026-07-17",
        resolved_date="2026-07-17",
        correlation_id="json-test",
        stages=(
            MaintenanceStageResult(
                name="test_stage",
                status=MaintenanceStageStatus.PARTIAL,
                counts={
                    "inserted": 100,
                    "updated": 50,
                    "quarantined": 5,
                },
                warnings=("Low coverage", "Stale data detected"),
            ),
        ),
        requested_symbols=(),
        successful_symbols=(),
        failed_symbols=(),
        diagnostics_refs=(),
        mutated=True,
    )

    started_at = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    completed_at = datetime(2026, 7, 17, 8, 1, tzinfo=timezone.utc)

    # When: persisting and retrieving
    run_id = persist_maintenance_run(
        conn,
        result,
        started_at=started_at,
        completed_at=completed_at,
        software_version="test",
    )
    stages = get_maintenance_run_stages(conn, run_id)

    # Then: JSON fields are properly deserialized
    assert stages[0]["counts"]["inserted"] == 100
    assert stages[0]["counts"]["quarantined"] == 5
    assert "Low coverage" in stages[0]["warnings"]
    assert "Stale data detected" in stages[0]["warnings"]
