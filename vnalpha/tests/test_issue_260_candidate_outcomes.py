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


def test_maturation_stamps_exact_lineage_references(conn) -> None:
    # Every matured outcome must carry exact RankingRun, eligible-universe and
    # factor-chain lineage references (#260).
    _seed_watchlist(conn, "2026-01-05", "FPT")
    _seed_bars(conn, "FPT", "2026-01-05", 70)
    _seed_bars(conn, "VNINDEX", "2026-01-05", 70, base=1000.0)

    service = DailyMaintenanceService(conn)
    stage = service._mature_candidate_outcomes("2026-05-01")
    assert stage.counts["lineage_updated"] > 0

    rows = conn.execute(
        """
        SELECT ranking_run_ref, eligible_universe_hash, factor_chain_hash
        FROM candidate_outcome WHERE symbol = 'FPT'
        """
    ).fetchall()
    assert rows
    for ranking_run_ref, universe_hash, factor_hash in rows:
        # RankingRun reference ties the outcome to the exact watchlist + policy.
        assert ranking_run_ref == "2026-01-05:hash123"
        # Universe and factor chain are content-addressed and never null.
        assert universe_hash and len(universe_hash) == 64
        assert factor_hash and len(factor_hash) == 64


def test_lineage_is_deterministic_and_idempotent(conn) -> None:
    # Re-running maturation recomputes identical lineage hashes and updates the
    # same rows in place (no duplicate rows, no hash drift).
    _seed_watchlist(conn, "2026-01-05", "FPT")
    _seed_bars(conn, "FPT", "2026-01-05", 70)
    _seed_bars(conn, "VNINDEX", "2026-01-05", 70, base=1000.0)

    service = DailyMaintenanceService(conn)
    service._mature_candidate_outcomes("2026-05-01")
    first = conn.execute(
        """
        SELECT symbol, horizon_sessions, eligible_universe_hash, factor_chain_hash
        FROM candidate_outcome ORDER BY horizon_sessions
        """
    ).fetchall()

    service._mature_candidate_outcomes("2026-05-01")
    second = conn.execute(
        """
        SELECT symbol, horizon_sessions, eligible_universe_hash, factor_chain_hash
        FROM candidate_outcome ORDER BY horizon_sessions
        """
    ).fetchall()

    assert first == second
    assert len(first) == len(second)


def test_lineage_reflects_point_in_time_universe(conn) -> None:
    # The eligible-universe hash is derived from the point-in-time classification
    # history, so two watchlist dates with different universes get distinct
    # universe hashes for the same symbol.
    conn.execute(
        """
        INSERT INTO symbol_classification_history (
            symbol, effective_from, effective_to, source_snapshot_id,
            classification_source, exchange, security_type, lifecycle_status,
            listing_date, delisting_date, sector_code, sector_name,
            industry_code, industry_name, taxonomy_name, taxonomy_version
        ) VALUES
            ('FPT', '2020-01-01 00:00:00+00', NULL, 'snap-a', 'fixture', 'HOSE',
             'COMMON_EQUITY', 'ACTIVE', NULL, NULL, 'TECH', 'Technology', NULL,
             NULL, 'ICB', 'icb-2026'),
            ('VCB', '2026-02-01 00:00:00+00', NULL, 'snap-b', 'fixture', 'HOSE',
             'COMMON_EQUITY', 'ACTIVE', NULL, NULL, 'BANK', 'Banks', NULL, NULL,
             'ICB', 'icb-2026')
        """
    )
    for day in ("2026-01-05", "2026-03-05"):
        _seed_watchlist(conn, day, "FPT")
    # One continuous bar series covers both watchlist dates and their forward
    # horizons without duplicating primary keys.
    _seed_bars(conn, "FPT", "2026-01-05", 120)
    _seed_bars(conn, "VNINDEX", "2026-01-05", 120, base=1000.0)

    service = DailyMaintenanceService(conn)
    service._mature_candidate_outcomes("2026-06-01")

    hashes = {
        r[0]: r[1]
        for r in conn.execute(
            """
            SELECT watchlist_date::VARCHAR, eligible_universe_hash
            FROM candidate_outcome WHERE symbol = 'FPT' AND horizon_sessions = 5
            """
        ).fetchall()
    }
    # VCB only becomes classifiable on 2026-02-01, so the resolved universe (and
    # therefore its content hash) differs between the two dates.
    assert hashes["2026-01-05"] != hashes["2026-03-05"]


def test_corporate_action_overlap_invalidates_outcome_deterministically(conn) -> None:
    # A confirmed corporate-action revision overlapping the outcome window must
    # deterministically mark the affected raw-basis outcome INVALID via the
    # maturation stage (#260: corporate-action revisions invalidate affected
    # outcomes deterministically).
    _seed_watchlist(conn, "2026-01-05", "FPT")
    _seed_bars(conn, "FPT", "2026-01-05", 70)
    _seed_bars(conn, "VNINDEX", "2026-01-05", 70, base=1000.0)
    conn.execute(
        """
        INSERT INTO corporate_action
            (revision_id, action_id, revision_number, symbol, action_type,
             ex_date, revision_hash, canonical_status, contract_version)
        VALUES ('rev-1', 'action-1', 1, 'FPT', 'CASH_DIVIDEND', '2026-01-08',
                'hash-1', 'CONFIRMED', 'v1')
        """
    )

    service = DailyMaintenanceService(conn)
    service._mature_candidate_outcomes("2026-05-01")
    statuses_first = conn.execute(
        "SELECT horizon_sessions, outcome_status FROM candidate_outcome "
        "WHERE symbol = 'FPT' ORDER BY horizon_sessions"
    ).fetchall()

    # The shortest horizon window overlaps the ex-date and must be INVALID.
    invalid = {h for h, s in statuses_first if s == "INVALID"}
    assert 5 in invalid

    # Re-maturation is deterministic: identical statuses, no duplicate rows.
    service._mature_candidate_outcomes("2026-05-01")
    statuses_second = conn.execute(
        "SELECT horizon_sessions, outcome_status FROM candidate_outcome "
        "WHERE symbol = 'FPT' ORDER BY horizon_sessions"
    ).fetchall()
    assert statuses_first == statuses_second
