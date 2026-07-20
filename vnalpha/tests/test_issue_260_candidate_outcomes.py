"""Tests for issue #260: deterministic candidate outcomes maturation stage.

The forward-outcome evaluator (MFE/MAE, benchmark-relative return, horizon
completeness, corporate-action invalidation, idempotent upsert) already exists.
Issue #260 adds the idempotent daily-maintenance stage that stages outcomes and
re-matures pending horizons. These tests cover that stage.
"""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.maintenance.daily import _PLANNED_STAGES, DailyMaintenanceService
from vnalpha.maintenance.models import MaintenanceStageStatus
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection, emit_observability=False)
    yield connection
    connection.close()


def _seed_watchlist(conn, date, symbol, rank=1):
    conn.execute(
        """
        INSERT INTO daily_watchlist
            (date, rank, symbol, score, candidate_class, setup_type,
             risk_flags_json, lineage_json, scoring_policy_id,
             scoring_policy_version, scoring_policy_hash, scoring_policy_status)
        VALUES (?, ?, ?, 0.9, 'PRIMARY', 'BREAKOUT', '[]', '{}',
                'baseline', 'v1', 'hash123', 'ACCEPTED')
        """,
        [date, rank, symbol],
    )


def _seed_bars(conn, symbol, start_day, count, base=100.0):
    from datetime import date, timedelta

    d = date.fromisoformat(start_day)
    added = 0
    cursor = d
    while added < count:
        if cursor.weekday() < 5:  # weekday only, mirrors sessions
            close = base + added
            conn.execute(
                """
                INSERT INTO canonical_ohlcv
                    (symbol, time, interval, open, high, low, close, volume,
                     selected_provider, price_basis, quality_status)
                VALUES (?, ?, '1D', ?, ?, ?, ?, 1000, 'vci', 'RAW_UNADJUSTED', 'OK')
                """,
                [
                    symbol,
                    f"{cursor.isoformat()} 00:00:00",
                    close,
                    close + 1,
                    close - 1,
                    close,
                ],
            )
            added += 1
        cursor += timedelta(days=1)


def test_candidate_outcomes_is_a_planned_stage() -> None:
    assert "candidate_outcomes" in _PLANNED_STAGES


def test_stage_skips_when_no_watchlist(conn) -> None:
    service = DailyMaintenanceService(conn)
    stage = service._mature_candidate_outcomes("2026-07-17")
    assert stage.name == "candidate_outcomes"
    assert stage.status is MaintenanceStageStatus.SKIPPED


def test_stage_matures_outcomes_and_is_idempotent(conn) -> None:
    # Watchlist on 2026-01-05 with enough forward bars for the shortest horizons.
    _seed_watchlist(conn, "2026-01-05", "FPT")
    _seed_bars(conn, "FPT", "2026-01-05", 70)
    _seed_bars(conn, "VNINDEX", "2026-01-05", 70, base=1000.0)

    service = DailyMaintenanceService(conn)
    stage1 = service._mature_candidate_outcomes("2026-05-01")
    assert stage1.status in (
        MaintenanceStageStatus.SUCCESS,
        MaintenanceStageStatus.PARTIAL,
    )
    assert stage1.counts["persisted"] > 0

    count1 = conn.execute("SELECT COUNT(*) FROM candidate_outcome").fetchone()[0]

    # Re-running does not duplicate rows (idempotent upsert).
    service._mature_candidate_outcomes("2026-05-01")
    count2 = conn.execute("SELECT COUNT(*) FROM candidate_outcome").fetchone()[0]
    assert count1 == count2
    assert count1 > 0


def test_pending_horizons_remain_pending_not_failed(conn) -> None:
    # Watchlist very recent: only a few forward bars exist, so long horizons
    # (T+20, T+60) cannot mature yet and must be PENDING, not errors.
    _seed_watchlist(conn, "2026-01-05", "FPT")
    _seed_bars(conn, "FPT", "2026-01-05", 8)  # only ~8 sessions forward
    _seed_bars(conn, "VNINDEX", "2026-01-05", 8, base=1000.0)

    service = DailyMaintenanceService(conn)
    stage = service._mature_candidate_outcomes("2026-01-16")
    assert stage.status is not MaintenanceStageStatus.FAILED

    statuses = {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT outcome_status FROM candidate_outcome WHERE symbol='FPT'"
        ).fetchall()
    }
    # At least one long horizon stays PENDING while the process succeeds.
    assert "PENDING" in statuses
