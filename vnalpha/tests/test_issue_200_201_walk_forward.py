import duckdb
import pytest

from vnalpha.outcomes.evaluator import evaluate_watchlist_date
from vnalpha.outcomes.repositories import get_candidate_outcomes
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn():
    c = in_memory_connection()
    run_migrations(conn=c)
    yield c
    c.close()


def _insert_ohlcv(conn: duckdb.DuckDBPyConnection, rows):
    for row in rows:
        conn.execute(
            """
            INSERT INTO canonical_ohlcv
                (symbol, time, interval, open, high, low, close, volume,
                 selected_provider, price_basis)
            VALUES (?, ?, '1D', ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (symbol, time, interval) DO NOTHING
            """,
            [
                row["symbol"],
                row["time"],
                row["close"],
                row["close"],
                row["close"],
                row["close"],
                100.0,
                "VCI",
                "RAW_UNADJUSTED",
            ],
        )


def _insert_watchlist(
    conn,
    symbol: str,
    watchlist_date: str,
    score: float,
):
    conn.execute(
        """
        INSERT INTO daily_watchlist
            (date, rank, symbol, score, candidate_class, setup_type,
             risk_flags_json, scoring_policy_id, scoring_policy_version,
             scoring_policy_hash, scoring_policy_status)
        VALUES (?, 1, ?, ?, 'STRONG_CANDIDATE', 'ACCUMULATION_BASE',
                '[]', ?, ?, ?, ?)
        ON CONFLICT (date, rank) DO UPDATE SET
            symbol=excluded.symbol,
            score=excluded.score,
            candidate_class=excluded.candidate_class,
            setup_type=excluded.setup_type,
            risk_flags_json=excluded.risk_flags_json,
            scoring_policy_id=excluded.scoring_policy_id,
            scoring_policy_version=excluded.scoring_policy_version,
            scoring_policy_hash=excluded.scoring_policy_hash,
            scoring_policy_status=excluded.scoring_policy_status
        """,
        [
            watchlist_date,
            symbol,
            score,
            BASELINE_SCORING_POLICY.policy_id,
            BASELINE_SCORING_POLICY.version,
            BASELINE_SCORING_POLICY.payload_hash,
            BASELINE_SCORING_POLICY.lifecycle_status.value,
        ],
    )


def test_walk_forward_entry_uses_next_session_for_symbol_and_benchmark(
    conn: duckdb.DuckDBPyConnection,
):
    _insert_ohlcv(
        conn,
        [
            {"symbol": "FPT", "time": "2026-01-01", "close": 100.0},
            {"symbol": "FPT", "time": "2026-01-02", "close": 110.0},
            {"symbol": "FPT", "time": "2026-01-03", "close": 120.0},
            {"symbol": "VNINDEX", "time": "2026-01-01", "close": 1000.0},
            {"symbol": "VNINDEX", "time": "2026-01-02", "close": 1100.0},
            {"symbol": "VNINDEX", "time": "2026-01-03", "close": 1200.0},
        ],
    )
    _insert_watchlist(conn, "FPT", "2026-01-01", 0.80)

    evaluate_watchlist_date(conn, "2026-01-01", horizons=[2])

    rows = get_candidate_outcomes(conn, "2026-01-01", 2)
    assert rows[0]["observation_start_date"] == "2026-01-02"
    assert rows[0]["observation_end_date"] == "2026-01-03"
    assert rows[0]["entry_close"] == 110.0
    assert rows[0]["exit_close"] == 120.0
    assert rows[0]["forward_return"] == pytest.approx(10.0 / 110.0)
    assert rows[0]["benchmark_return"] == pytest.approx(100.0 / 1100.0)


def test_multiple_horizons_produce_period_specific_statuses(
    conn: duckdb.DuckDBPyConnection,
):
    _insert_ohlcv(
        conn,
        [
            {"symbol": "FPT", "time": "2026-01-01", "close": 100.0},
            {"symbol": "FPT", "time": "2026-01-02", "close": 110.0},
            {"symbol": "FPT", "time": "2026-01-03", "close": 120.0},
            {"symbol": "FPT", "time": "2026-01-04", "close": 130.0},
            {"symbol": "VNINDEX", "time": "2026-01-01", "close": 1000.0},
            {"symbol": "VNINDEX", "time": "2026-01-02", "close": 1050.0},
        ],
    )
    _insert_watchlist(conn, "FPT", "2026-01-01", 0.80)

    evaluate_watchlist_date(conn, "2026-01-01", horizons=[1, 3])

    rows = {
        1: get_candidate_outcomes(conn, "2026-01-01", 1)[0],
        3: get_candidate_outcomes(conn, "2026-01-01", 3)[0],
    }

    assert rows[1]["outcome_status"] == "COMPLETE"
    assert rows[1]["observation_end_date"] == "2026-01-02"
    assert rows[1]["forward_return"] == pytest.approx(0.0)

    assert rows[3]["outcome_status"] == "PARTIAL"
    assert rows[3]["observation_end_date"] == "2026-01-04"
    assert rows[3]["forward_return"] == pytest.approx(20.0 / 110.0)


def test_exclusion_is_applied_per_horizon_for_invalid_lineage(
    conn: duckdb.DuckDBPyConnection,
):
    _insert_ohlcv(
        conn,
        [
            {"symbol": "FPT", "time": "2026-01-01", "close": 100.0},
            {"symbol": "FPT", "time": "2026-01-02", "close": 110.0},
            {"symbol": "FPT", "time": "2026-01-03", "close": 120.0},
            {"symbol": "VNINDEX", "time": "2026-01-01", "close": 1000.0},
            {"symbol": "VNINDEX", "time": "2026-01-02", "close": 1050.0},
            {"symbol": "VNINDEX", "time": "2026-01-03", "close": 1100.0},
        ],
    )
    conn.execute(
        """UPDATE canonical_ohlcv
SET price_basis='ADJUSTED'
WHERE symbol='FPT' AND time='2026-01-02'
"""
    )
    _insert_watchlist(conn, "FPT", "2026-01-01", 0.80)

    evaluate_watchlist_date(conn, "2026-01-01", horizons=[1, 2])

    rows_1 = get_candidate_outcomes(conn, "2026-01-01", 1)[0]
    rows_2 = get_candidate_outcomes(conn, "2026-01-01", 2)[0]

    assert rows_1["outcome_status"] == "INVALID"
    assert rows_2["outcome_status"] == "INVALID"
    assert "price basis" in rows_1["invalidation_reason"]
    assert "price basis" in rows_2["invalidation_reason"]


def test_failure_boundary_records_missing_symbol_data_for_all_horizons(
    conn: duckdb.DuckDBPyConnection,
):
    _insert_ohlcv(
        conn,
        [
            {"symbol": "VNINDEX", "time": "2026-01-01", "close": 1000.0},
            {"symbol": "VNINDEX", "time": "2026-01-02", "close": 1050.0},
            {"symbol": "VNINDEX", "time": "2026-01-03", "close": 1100.0},
        ],
    )
    _insert_watchlist(conn, "FPT", "2026-01-01", 0.80)

    evaluate_watchlist_date(conn, "2026-01-01", horizons=[1, 3])

    rows = {
        1: get_candidate_outcomes(conn, "2026-01-01", 1)[0],
        3: get_candidate_outcomes(conn, "2026-01-01", 3)[0],
    }

    assert rows[1]["outcome_status"] == "MISSING_DATA"
    assert rows[3]["outcome_status"] == "MISSING_DATA"
