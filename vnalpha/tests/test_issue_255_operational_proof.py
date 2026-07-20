"""Tests for issue #255: operational-proof aggregation over the ledger.

The 10 live consecutive sessions themselves are operator-owned evidence (real
trading days + live providers). This covers the code-satisfiable part: an
aggregator that truthfully summarises whatever the ledger recorded into the
required proof shape, and fails closed when the sessions are not yet present.
"""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import pytest

from vnalpha.maintenance.ledger import (
    collect_operational_proof,
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


def _persist(conn, date, *, status=MaintenanceRunStatus.SUCCESS, hour=8, corr=None):
    result = DailyMaintenanceResult(
        status=status,
        requested_date=date,
        resolved_date=date,
        correlation_id=corr or f"corr-{date}-{hour}",
        stages=(
            MaintenanceStageResult("resolve_session", MaintenanceStageStatus.SUCCESS),
        ),
        requested_symbols=("VCB",),
        successful_symbols=("VCB",),
        failed_symbols=(),
        diagnostics_refs=(),
        mutated=True,
    )
    persist_maintenance_run(
        conn,
        result,
        started_at=datetime(2026, 1, 1, hour, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, hour, 5, tzinfo=timezone.utc),
        software_version="test",
    )


def test_empty_ledger_is_not_proven(conn) -> None:
    report = collect_operational_proof(conn, required_sessions=10)
    assert report["distinct_sessions_recorded"] == 0
    assert report["has_required_sessions"] is False
    assert report["session_dates"] == []


def test_ten_distinct_sessions_are_proven(conn) -> None:
    for day in range(5, 15):  # 10 distinct dates
        _persist(conn, f"2026-01-{day:02d}")
    report = collect_operational_proof(conn, required_sessions=10)
    assert report["distinct_sessions_recorded"] == 10
    assert report["has_required_sessions"] is True
    assert len(report["sessions"]) == 10


def test_fewer_than_required_fails_closed(conn) -> None:
    for day in range(5, 10):  # only 5 distinct dates
        _persist(conn, f"2026-01-{day:02d}")
    report = collect_operational_proof(conn, required_sessions=10)
    assert report["has_required_sessions"] is False
    assert report["distinct_sessions_recorded"] == 5


def test_same_date_reruns_collapse_and_are_flagged(conn) -> None:
    # Two invocations for the same date must count as one session but be flagged.
    _persist(conn, "2026-01-05", hour=8, corr="first")
    _persist(conn, "2026-01-05", hour=9, corr="second")
    _persist(conn, "2026-01-06", hour=8, corr="third")
    report = collect_operational_proof(conn, required_sessions=10)
    assert report["distinct_sessions_recorded"] == 2
    assert "2026-01-05" in report["same_date_rerun_dates"]
    # The latest invocation for the reran date is surfaced.
    session = next(s for s in report["sessions"] if s["resolved_date"] == "2026-01-05")
    assert session["correlation_id"] == "second"
    assert session["same_date_invocations"] == 2


def test_cli_proof_exits_nonzero_when_unproven(conn) -> None:
    from typer.testing import CliRunner

    from vnalpha.cli import app

    result = CliRunner().invoke(app, ["maintain", "proof", "--json"])
    # Fresh warehouse -> no sessions -> non-zero exit.
    assert result.exit_code == 1
