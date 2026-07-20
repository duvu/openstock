"""Tests for issue #262: deterministic point-in-time ranking replay."""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.replay import (
    ReplayContaminationError,
    ReplaySpec,
    get_replay,
    run_replay,
)
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection, emit_observability=False)
    yield connection
    connection.close()


def _seed_outcome(
    conn, symbol, date, rank, excess, *, horizon=20, status="COMPLETE", sector="TECH"
):
    conn.execute(
        "INSERT INTO symbol_master (symbol, sector_code, is_active) VALUES (?, ?, TRUE) "
        "ON CONFLICT DO NOTHING",
        [symbol, sector],
    )
    conn.execute(
        """
        INSERT INTO candidate_outcome
            (symbol, watchlist_date, horizon_sessions, rank, score,
             excess_return_vs_vnindex, outcome_status, price_basis,
             scoring_policy_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'RAW_UNADJUSTED', 'hash123')
        """,
        [symbol, date, horizon, rank, 1.0 / rank, excess, status],
    )


def _seed_period(conn, date, n=5, base_excess=0.05):
    for i in range(1, n + 1):
        _seed_outcome(conn, f"S{i}", date, rank=i, excess=base_excess + 0.01 * (n - i))


def test_spec_content_hash_is_stable() -> None:
    spec1 = ReplaySpec(
        start_date="2026-01-05", end_date="2026-01-30", horizon_sessions=20, top_n=3
    )
    spec2 = ReplaySpec(
        start_date="2026-01-05", end_date="2026-01-30", horizon_sessions=20, top_n=3
    )
    spec3 = ReplaySpec(
        start_date="2026-01-05", end_date="2026-01-30", horizon_sessions=20, top_n=5
    )
    assert spec1.content_hash() == spec2.content_hash()
    assert spec1.content_hash() != spec3.content_hash()


def test_identical_inputs_reproduce_identical_results(conn) -> None:
    _seed_period(conn, "2026-01-05")
    _seed_period(conn, "2026-01-06")
    spec = ReplaySpec(
        start_date="2026-01-05", end_date="2026-01-31", horizon_sessions=20, top_n=3
    )
    r1 = run_replay(conn, spec)
    r2 = run_replay(conn, spec)
    assert r1.result_hash == r2.result_hash
    assert r1.dataset_hash == r2.dataset_hash
    assert r1.period_count == 2


def test_future_data_contamination_fails_closed(conn) -> None:
    # One period has a still-pending (immature) outcome -> replay must fail closed.
    _seed_period(conn, "2026-01-05")
    _seed_outcome(conn, "PENDINGX", "2026-01-05", rank=99, excess=0.0, status="PENDING")
    spec = ReplaySpec(
        start_date="2026-01-05", end_date="2026-01-31", horizon_sessions=20, top_n=3
    )
    with pytest.raises(ReplayContaminationError):
        run_replay(conn, spec)


def test_assumptions_and_exclusions_are_explicit(conn) -> None:
    spec = ReplaySpec(
        start_date="2026-01-05", end_date="2026-01-31", horizon_sessions=20, top_n=3
    )
    result = run_replay(conn, spec)
    # No data at all -> zero periods, explicit caveat, no fabricated returns.
    assert result.period_count == 0
    assert "no_replayable_periods" in result.caveats
    assert result.total_return is None


def test_content_addressed_artifact_is_immutable(conn) -> None:
    _seed_period(conn, "2026-01-05")
    spec = ReplaySpec(
        start_date="2026-01-05", end_date="2026-01-31", horizon_sessions=20, top_n=3
    )
    run_replay(conn, spec)
    run_replay(conn, spec)
    count = conn.execute("SELECT COUNT(*) FROM ranking_replay").fetchone()[0]
    assert count == 1


def test_cli_and_persisted_read_agree(conn) -> None:
    _seed_period(conn, "2026-01-05")
    _seed_period(conn, "2026-01-06")
    spec = ReplaySpec(
        start_date="2026-01-05", end_date="2026-01-31", horizon_sessions=20, top_n=3
    )
    result = run_replay(conn, spec)
    fetched = get_replay(conn, result.replay_id)
    assert fetched is not None
    assert fetched["result_hash"] == result.result_hash
    assert fetched["period_count"] == 2


def test_cost_reduces_net_return(conn) -> None:
    # Two periods with full turnover; a positive cost lowers net excess.
    _seed_period(conn, "2026-01-05")
    conn.execute("DELETE FROM candidate_outcome WHERE watchlist_date='2026-01-06'")
    for i in range(1, 6):
        _seed_outcome(conn, f"T{i}", "2026-01-06", rank=i, excess=0.05)

    free = run_replay(
        conn,
        ReplaySpec(
            start_date="2026-01-05",
            end_date="2026-01-31",
            horizon_sessions=20,
            top_n=3,
            cost_bps=0.0,
        ),
        persist=False,
    )
    costly = run_replay(
        conn,
        ReplaySpec(
            start_date="2026-01-05",
            end_date="2026-01-31",
            horizon_sessions=20,
            top_n=3,
            cost_bps=100.0,
        ),
        persist=False,
    )
    assert costly.total_return is not None and free.total_return is not None
    assert costly.total_return <= free.total_return
