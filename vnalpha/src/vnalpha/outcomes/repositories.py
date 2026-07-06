"""Repository helpers for outcome tables."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import duckdb

from vnalpha.outcomes.models import (
    CandidateOutcomeRecord,
    RiskFlagPerformanceRecord,
    ScoreBucketPerformanceRecord,
    SetupTypePerformanceRecord,
    WatchlistOutcomeRecord,
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- candidate_outcome ----

def upsert_candidate_outcome(conn: duckdb.DuckDBPyConnection, rec: CandidateOutcomeRecord) -> None:
    """Upsert one candidate outcome row."""
    if rec.computed_at is None:
        rec.computed_at = _now_utc()
    conn.execute(
        """
        INSERT INTO candidate_outcome VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
        ON CONFLICT (symbol, watchlist_date, horizon_sessions)
        DO UPDATE SET
            rank=excluded.rank, score=excluded.score,
            candidate_class=excluded.candidate_class,
            setup_type=excluded.setup_type,
            risk_flags_json=excluded.risk_flags_json,
            entry_close=excluded.entry_close,
            exit_close=excluded.exit_close,
            benchmark_entry_close=excluded.benchmark_entry_close,
            benchmark_exit_close=excluded.benchmark_exit_close,
            forward_return=excluded.forward_return,
            benchmark_return=excluded.benchmark_return,
            excess_return_vs_vnindex=excluded.excess_return_vs_vnindex,
            max_gain=excluded.max_gain, max_drawdown=excluded.max_drawdown,
            hit=excluded.hit, failure=excluded.failure,
            outcome_status=excluded.outcome_status,
            bars_available=excluded.bars_available,
            required_bars=excluded.required_bars,
            computed_at=excluded.computed_at,
            error_json=excluded.error_json
        """,
        [
            rec.symbol, rec.watchlist_date, rec.horizon_sessions,
            rec.rank, rec.score, rec.candidate_class, rec.setup_type,
            rec.risk_flags_json, rec.entry_close, rec.exit_close,
            rec.benchmark_entry_close, rec.benchmark_exit_close,
            rec.forward_return, rec.benchmark_return,
            rec.excess_return_vs_vnindex, rec.max_gain, rec.max_drawdown,
            rec.hit, rec.failure, rec.outcome_status,
            rec.bars_available, rec.required_bars,
            rec.computed_at, rec.error_json,
        ],
    )


def get_candidate_outcomes(
    conn: duckdb.DuckDBPyConnection,
    watchlist_date: str,
    horizon_sessions: int,
) -> List[Dict[str, Any]]:
    """List candidate outcomes for a date and horizon."""
    rows = conn.execute(
        """
        SELECT symbol, watchlist_date::VARCHAR, horizon_sessions, rank, score,
               candidate_class, setup_type, risk_flags_json,
               entry_close, exit_close, benchmark_entry_close, benchmark_exit_close,
               forward_return, benchmark_return, excess_return_vs_vnindex,
               max_gain, max_drawdown, hit, failure, outcome_status,
               bars_available, required_bars, computed_at::VARCHAR, error_json
        FROM candidate_outcome
        WHERE watchlist_date = ? AND horizon_sessions = ?
        ORDER BY score DESC NULLS LAST
        """,
        [watchlist_date, horizon_sessions],
    ).fetchall()
    cols = [
        "symbol", "watchlist_date", "horizon_sessions", "rank", "score",
        "candidate_class", "setup_type", "risk_flags_json",
        "entry_close", "exit_close", "benchmark_entry_close", "benchmark_exit_close",
        "forward_return", "benchmark_return", "excess_return_vs_vnindex",
        "max_gain", "max_drawdown", "hit", "failure", "outcome_status",
        "bars_available", "required_bars", "computed_at", "error_json",
    ]
    return [dict(zip(cols, r, strict=True)) for r in rows]


# ---- watchlist_outcome ----

def upsert_watchlist_outcome(conn: duckdb.DuckDBPyConnection, rec: WatchlistOutcomeRecord) -> None:
    if rec.computed_at is None:
        rec.computed_at = _now_utc()
    conn.execute(
        """
        INSERT INTO watchlist_outcome VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (watchlist_date, horizon_sessions)
        DO UPDATE SET
            candidate_count=excluded.candidate_count,
            complete_count=excluded.complete_count,
            pending_count=excluded.pending_count,
            missing_data_count=excluded.missing_data_count,
            avg_forward_return=excluded.avg_forward_return,
            median_forward_return=excluded.median_forward_return,
            avg_excess_return=excluded.avg_excess_return,
            median_excess_return=excluded.median_excess_return,
            avg_max_gain=excluded.avg_max_gain,
            avg_max_drawdown=excluded.avg_max_drawdown,
            hit_rate=excluded.hit_rate,
            failure_rate=excluded.failure_rate,
            computed_at=excluded.computed_at
        """,
        [
            rec.watchlist_date, rec.horizon_sessions,
            rec.candidate_count, rec.complete_count,
            rec.pending_count, rec.missing_data_count,
            rec.avg_forward_return, rec.median_forward_return,
            rec.avg_excess_return, rec.median_excess_return,
            rec.avg_max_gain, rec.avg_max_drawdown,
            rec.hit_rate, rec.failure_rate, rec.computed_at,
        ],
    )


def get_watchlist_outcome(
    conn: duckdb.DuckDBPyConnection,
    watchlist_date: str,
    horizon_sessions: int,
) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT watchlist_date::VARCHAR, horizon_sessions, candidate_count,
               complete_count, pending_count, missing_data_count,
               avg_forward_return, median_forward_return,
               avg_excess_return, median_excess_return,
               avg_max_gain, avg_max_drawdown, hit_rate, failure_rate,
               computed_at::VARCHAR
        FROM watchlist_outcome
        WHERE watchlist_date = ? AND horizon_sessions = ?
        """,
        [watchlist_date, horizon_sessions],
    ).fetchone()
    if row is None:
        return None
    cols = [
        "watchlist_date", "horizon_sessions", "candidate_count",
        "complete_count", "pending_count", "missing_data_count",
        "avg_forward_return", "median_forward_return",
        "avg_excess_return", "median_excess_return",
        "avg_max_gain", "avg_max_drawdown", "hit_rate", "failure_rate", "computed_at",
    ]
    return dict(zip(cols, row, strict=True))


# ---- score_bucket_performance ----

def upsert_score_bucket_performance(conn: duckdb.DuckDBPyConnection, rec: ScoreBucketPerformanceRecord) -> None:
    if rec.computed_at is None:
        rec.computed_at = _now_utc()
    conn.execute(
        """
        INSERT INTO score_bucket_performance VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (as_of_date, horizon_sessions, score_bucket)
        DO UPDATE SET
            candidate_count=excluded.candidate_count,
            avg_forward_return=excluded.avg_forward_return,
            median_forward_return=excluded.median_forward_return,
            avg_excess_return=excluded.avg_excess_return,
            hit_rate=excluded.hit_rate,
            failure_rate=excluded.failure_rate,
            avg_max_drawdown=excluded.avg_max_drawdown,
            computed_at=excluded.computed_at
        """,
        [
            rec.as_of_date, rec.horizon_sessions, rec.score_bucket,
            rec.candidate_count, rec.avg_forward_return, rec.median_forward_return,
            rec.avg_excess_return, rec.hit_rate, rec.failure_rate,
            rec.avg_max_drawdown, rec.computed_at,
        ],
    )


def list_score_bucket_performance(
    conn: duckdb.DuckDBPyConnection,
    horizon_sessions: int,
    as_of_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    sql = """
        SELECT as_of_date::VARCHAR, horizon_sessions, score_bucket, candidate_count,
               avg_forward_return, median_forward_return, avg_excess_return,
               hit_rate, failure_rate, avg_max_drawdown, computed_at::VARCHAR
        FROM score_bucket_performance
        WHERE horizon_sessions = ?
    """
    params: List[Any] = [horizon_sessions]
    if as_of_date:
        sql += " AND as_of_date = ?"
        params.append(as_of_date)
    sql += " ORDER BY score_bucket"
    rows = conn.execute(sql, params).fetchall()
    cols = [
        "as_of_date", "horizon_sessions", "score_bucket", "candidate_count",
        "avg_forward_return", "median_forward_return", "avg_excess_return",
        "hit_rate", "failure_rate", "avg_max_drawdown", "computed_at",
    ]
    return [dict(zip(cols, r, strict=True)) for r in rows]


# ---- setup_type_performance ----

def upsert_setup_type_performance(conn: duckdb.DuckDBPyConnection, rec: SetupTypePerformanceRecord) -> None:
    if rec.computed_at is None:
        rec.computed_at = _now_utc()
    conn.execute(
        """
        INSERT INTO setup_type_performance VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (as_of_date, horizon_sessions, setup_type)
        DO UPDATE SET
            candidate_count=excluded.candidate_count,
            avg_forward_return=excluded.avg_forward_return,
            median_forward_return=excluded.median_forward_return,
            avg_excess_return=excluded.avg_excess_return,
            hit_rate=excluded.hit_rate,
            failure_rate=excluded.failure_rate,
            avg_max_drawdown=excluded.avg_max_drawdown,
            computed_at=excluded.computed_at
        """,
        [
            rec.as_of_date, rec.horizon_sessions, rec.setup_type,
            rec.candidate_count, rec.avg_forward_return, rec.median_forward_return,
            rec.avg_excess_return, rec.hit_rate, rec.failure_rate,
            rec.avg_max_drawdown, rec.computed_at,
        ],
    )


def list_setup_type_performance(
    conn: duckdb.DuckDBPyConnection,
    horizon_sessions: int,
    as_of_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    sql = """
        SELECT as_of_date::VARCHAR, horizon_sessions, setup_type, candidate_count,
               avg_forward_return, median_forward_return, avg_excess_return,
               hit_rate, failure_rate, avg_max_drawdown, computed_at::VARCHAR
        FROM setup_type_performance
        WHERE horizon_sessions = ?
    """
    params: List[Any] = [horizon_sessions]
    if as_of_date:
        sql += " AND as_of_date = ?"
        params.append(as_of_date)
    sql += " ORDER BY setup_type"
    rows = conn.execute(sql, params).fetchall()
    cols = [
        "as_of_date", "horizon_sessions", "setup_type", "candidate_count",
        "avg_forward_return", "median_forward_return", "avg_excess_return",
        "hit_rate", "failure_rate", "avg_max_drawdown", "computed_at",
    ]
    return [dict(zip(cols, r, strict=True)) for r in rows]


# ---- risk_flag_performance ----

def upsert_risk_flag_performance(conn: duckdb.DuckDBPyConnection, rec: RiskFlagPerformanceRecord) -> None:
    if rec.computed_at is None:
        rec.computed_at = _now_utc()
    conn.execute(
        """
        INSERT INTO risk_flag_performance VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (as_of_date, horizon_sessions, risk_flag)
        DO UPDATE SET
            candidate_count=excluded.candidate_count,
            avg_forward_return=excluded.avg_forward_return,
            median_forward_return=excluded.median_forward_return,
            avg_excess_return=excluded.avg_excess_return,
            hit_rate=excluded.hit_rate,
            failure_rate=excluded.failure_rate,
            avg_max_drawdown=excluded.avg_max_drawdown,
            computed_at=excluded.computed_at
        """,
        [
            rec.as_of_date, rec.horizon_sessions, rec.risk_flag,
            rec.candidate_count, rec.avg_forward_return, rec.median_forward_return,
            rec.avg_excess_return, rec.hit_rate, rec.failure_rate,
            rec.avg_max_drawdown, rec.computed_at,
        ],
    )


def list_risk_flag_performance(
    conn: duckdb.DuckDBPyConnection,
    horizon_sessions: int,
    as_of_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    sql = """
        SELECT as_of_date::VARCHAR, horizon_sessions, risk_flag, candidate_count,
               avg_forward_return, median_forward_return, avg_excess_return,
               hit_rate, failure_rate, avg_max_drawdown, computed_at::VARCHAR
        FROM risk_flag_performance
        WHERE horizon_sessions = ?
    """
    params: List[Any] = [horizon_sessions]
    if as_of_date:
        sql += " AND as_of_date = ?"
        params.append(as_of_date)
    sql += " ORDER BY risk_flag"
    rows = conn.execute(sql, params).fetchall()
    cols = [
        "as_of_date", "horizon_sessions", "risk_flag", "candidate_count",
        "avg_forward_return", "median_forward_return", "avg_excess_return",
        "hit_rate", "failure_rate", "avg_max_drawdown", "computed_at",
    ]
    return [dict(zip(cols, r, strict=True)) for r in rows]
