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


# Ten consecutive Vietnamese trading sessions (VietnamSessionCalendar) used to
# build a genuinely provable ledger window in tests.
_CONSECUTIVE_SESSIONS = (
    "2026-01-05",
    "2026-01-06",
    "2026-01-07",
    "2026-01-08",
    "2026-01-09",
    "2026-01-12",
    "2026-01-13",
    "2026-01-14",
    "2026-01-15",
    "2026-01-16",
)


def _persist(
    conn,
    date,
    *,
    status=MaintenanceRunStatus.SUCCESS,
    hour=8,
    corr=None,
    identity=False,
    source_policy=None,
):
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
        package_version="1.0.0" if identity else None,
        source_commit="deadbeef" if identity else None,
        calendar_version="vn-2026" if identity else None,
        source_policy=source_policy,
    )


def _persist_provable_window(conn):
    """Seed a fully provable 10-session window: consecutive real sessions with
    complete software identity, resolved source policy, and two same-date
    reruns (matching the #255 acceptance evidence contract)."""
    policy = {"equity.ohlcv": {"source": None, "mode": "AUTO"}}
    for index, day in enumerate(_CONSECUTIVE_SESSIONS):
        _persist(conn, day, identity=True, source_policy=policy)
        # Two of the sessions receive a same-date manual rerun.
        if index < 2:
            _persist(
                conn,
                day,
                hour=9,
                corr=f"rerun-{day}",
                identity=True,
                source_policy=policy,
            )


def test_empty_ledger_is_not_proven(conn) -> None:
    report = collect_operational_proof(conn, required_sessions=10)
    assert report["distinct_sessions_recorded"] == 0
    assert report["has_required_sessions"] is False
    assert report["session_dates"] == []


def test_ten_distinct_sessions_are_proven(conn) -> None:
    # A fully provable window: 10 consecutive real trading sessions with
    # complete identity, resolved source policy and two same-date reruns.
    _persist_provable_window(conn)
    report = collect_operational_proof(conn, required_sessions=10)
    assert report["distinct_sessions_recorded"] == 10
    assert report["has_required_sessions"] is True
    assert report["consecutive_market_sessions"] is True
    assert report["identity_complete"] is True
    assert report["source_policy_complete"] is True
    assert len(report["same_date_rerun_dates"]) >= 2
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
