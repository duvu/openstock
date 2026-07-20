"""Tests for deterministic point-in-time ranking replay v2."""

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


def _seed_classification(conn, symbol, sector="TECH"):
    conn.execute(
        """
        INSERT INTO symbol_classification_history (
            symbol, effective_from, source_snapshot_id, classification_source,
            exchange, security_type, lifecycle_status, listing_date,
            sector_code, sector_name, taxonomy_name, taxonomy_version
        ) SELECT ?, '2020-01-01', ?, 'fixture', 'HOSE', 'STOCK', 'ACTIVE',
                 '2020-01-01', ?, ?, 'ICB', 'v1'
        WHERE NOT EXISTS (
            SELECT 1 FROM symbol_classification_history WHERE symbol = ?
        )
        """,
        [symbol, f"snapshot-{symbol}", sector, sector, symbol],
    )


def _seed_outcome(
    conn,
    symbol,
    day,
    rank,
    excess,
    *,
    horizon=20,
    status="COMPLETE",
    sector="TECH",
    policy_hash="hash123",
):
    _seed_classification(conn, symbol, sector)
    conn.execute(
        """
        INSERT INTO candidate_outcome (
            symbol, watchlist_date, horizon_sessions, rank, score,
            excess_return_vs_vnindex, outcome_status, price_basis,
            adjustment_version, scoring_policy_id, scoring_policy_version,
            scoring_policy_hash, computed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'RAW_UNADJUSTED', 'NONE',
                  'baseline', 'v2', ?, CAST(? AS DATE) + INTERVAL 30 DAY)
        """,
        [symbol, day, horizon, rank, 1.0 / rank, excess, status, policy_hash, day],
    )


def _seed_period(conn, day, n=5, base_excess=0.05, prefix="S"):
    for index in range(1, n + 1):
        _seed_outcome(
            conn,
            f"{prefix}{index}",
            day,
            rank=index,
            excess=base_excess + 0.01 * (n - index),
        )


def test_spec_content_hash_is_stable() -> None:
    spec1 = ReplaySpec(
        start_date="2026-01-05",
        end_date="2026-01-30",
        horizon_sessions=20,
        top_n=3,
    )
    spec2 = ReplaySpec(
        start_date="2026-01-05",
        end_date="2026-01-30",
        horizon_sessions=20,
        top_n=3,
    )
    spec3 = ReplaySpec(
        start_date="2026-01-05",
        end_date="2026-01-30",
        horizon_sessions=20,
        top_n=5,
    )
    assert spec1.content_hash() == spec2.content_hash()
    assert spec1.content_hash() != spec3.content_hash()


def test_identical_inputs_reproduce_identical_results(conn) -> None:
    _seed_period(conn, "2026-01-05")
    _seed_period(conn, "2026-01-06")
    spec = ReplaySpec(
        start_date="2026-01-05",
        end_date="2026-01-31",
        horizon_sessions=20,
        top_n=3,
        scoring_policy_hash="hash123",
    )
    first = run_replay(conn, spec)
    second = run_replay(conn, spec)
    assert first.result_hash == second.result_hash
    assert first.dataset_hash == second.dataset_hash
    assert first.period_count == 2
    assert first.total_return == pytest.approx((1 + first.periods[0].period_excess_return) * (1 + first.periods[1].period_excess_return) - 1)


def test_future_data_contamination_fails_closed(conn) -> None:
    _seed_period(conn, "2026-01-05")
    _seed_outcome(
        conn,
        "PENDINGX",
        "2026-01-05",
        rank=99,
        excess=0.0,
        status="PENDING",
    )
    spec = ReplaySpec(
        start_date="2026-01-05",
        end_date="2026-01-31",
        horizon_sessions=20,
        top_n=3,
    )
    with pytest.raises(ReplayContaminationError):
        run_replay(conn, spec)


def test_mixed_policy_fails_closed(conn) -> None:
    _seed_period(conn, "2026-01-05")
    _seed_outcome(
        conn,
        "OTHER",
        "2026-01-05",
        rank=9,
        excess=0.01,
        policy_hash="other-hash",
    )
    with pytest.raises(ReplayContaminationError, match="policy"):
        run_replay(
            conn,
            ReplaySpec(
                start_date="2026-01-05",
                end_date="2026-01-31",
                horizon_sessions=20,
                top_n=3,
            ),
        )


def test_symbol_outside_point_in_time_universe_fails_closed(conn) -> None:
    _seed_period(conn, "2026-01-05")
    conn.execute("DELETE FROM symbol_classification_history WHERE symbol = 'S3'")
    with pytest.raises(ReplayContaminationError, match="point-in-time universe"):
        run_replay(
            conn,
            ReplaySpec(
                start_date="2026-01-05",
                end_date="2026-01-31",
                horizon_sessions=20,
                top_n=3,
            ),
        )


def test_unsupported_benchmark_fails_closed(conn) -> None:
    with pytest.raises(ReplayContaminationError, match="VNINDEX-relative"):
        run_replay(
            conn,
            ReplaySpec(
                start_date="2026-01-05",
                end_date="2026-01-31",
                horizon_sessions=20,
                top_n=3,
                benchmark_symbol="HNXINDEX",
            ),
        )


def test_assumptions_and_exclusions_are_explicit(conn) -> None:
    result = run_replay(
        conn,
        ReplaySpec(
            start_date="2026-01-05",
            end_date="2026-01-31",
            horizon_sessions=20,
            top_n=3,
        ),
    )
    assert result.period_count == 0
    assert "no_replayable_periods" in result.caveats
    assert result.total_return is None


def test_content_addressed_artifact_is_immutable(conn) -> None:
    _seed_period(conn, "2026-01-05")
    spec = ReplaySpec(
        start_date="2026-01-05",
        end_date="2026-01-31",
        horizon_sessions=20,
        top_n=3,
    )
    run_replay(conn, spec)
    run_replay(conn, spec)
    count = conn.execute("SELECT COUNT(*) FROM ranking_replay_v2").fetchone()[0]
    assert count == 1


def test_persisted_read_agrees_and_event_ledger_is_present(conn) -> None:
    _seed_period(conn, "2026-01-05")
    _seed_period(conn, "2026-01-06", prefix="T")
    result = run_replay(
        conn,
        ReplaySpec(
            start_date="2026-01-05",
            end_date="2026-01-31",
            horizon_sessions=20,
            top_n=3,
        ),
    )
    fetched = get_replay(conn, result.replay_id)
    assert fetched is not None
    assert fetched["result_hash"] == result.result_hash
    assert fetched["period_count"] == 2
    assert len(fetched["event_ledger"]) == 2


def test_cost_reduces_compounded_return(conn) -> None:
    _seed_period(conn, "2026-01-05", prefix="S")
    _seed_period(conn, "2026-01-06", prefix="T")
    common = dict(
        start_date="2026-01-05",
        end_date="2026-01-31",
        horizon_sessions=20,
        top_n=3,
    )
    free = run_replay(conn, ReplaySpec(**common, cost_bps=0.0), persist=False)
    costly = run_replay(conn, ReplaySpec(**common, cost_bps=100.0), persist=False)
    assert costly.total_return is not None and free.total_return is not None
    assert costly.total_return < free.total_return
