"""Repository helpers for outcome tables."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import duckdb

from vnalpha.features.status import feature_eligibility_sql
from vnalpha.outcomes.models import (
    OUTCOME_EVALUATION_ASSUMPTIONS_CONTRACT_VERSION,
    OUTCOME_EVALUATION_ASSUMPTIONS_HASH,
    OUTCOME_EVALUATION_ASSUMPTIONS_PAYLOAD_JSON,
    CandidateOutcomeRecord,
    HypothesisOutcomeSummary,
    OutcomeStatus,
    RiskFlagPerformanceRecord,
    ScoreBucketPerformanceRecord,
    SetupTypePerformanceRecord,
    WatchlistOutcomeRecord,
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- outcome_evaluation_run ----


def create_evaluation_run(
    conn: duckdb.DuckDBPyConnection,
    watchlist_date: str,
    evaluator_version: Optional[str],
    metric_policy_version: Optional[str],
    horizons: List[int],
    assumptions_contract_version: str = OUTCOME_EVALUATION_ASSUMPTIONS_CONTRACT_VERSION,
    assumptions_payload_json: str = OUTCOME_EVALUATION_ASSUMPTIONS_PAYLOAD_JSON,
    assumptions_hash: str = OUTCOME_EVALUATION_ASSUMPTIONS_HASH,
    price_basis: str = "UNKNOWN",
    adjustment_methodology: str = "UNKNOWN",
    adjustment_version: str = "UNKNOWN",
    action_overlap_status: str = "NOT_EVALUATED",
    scoring_policy_id: str | None = None,
    scoring_policy_version: str | None = None,
    scoring_policy_hash: str | None = None,
    scoring_policy_status: str | None = None,
) -> str:
    """Insert a new RUNNING evaluation run record; return its ID."""
    run_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO outcome_evaluation_run
            (evaluation_run_id, watchlist_date, started_at, status,
             assumptions_contract_version, assumptions_payload_json,
             assumptions_hash, evaluator_version, metric_policy_version,
             horizons_json,
             price_basis, adjustment_methodology, adjustment_version,
             action_overlap_status, scoring_policy_id, scoring_policy_version,
             scoring_policy_hash, scoring_policy_status)
        VALUES (?, ?, ?, 'RUNNING', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            watchlist_date,
            _now_utc(),
            assumptions_contract_version,
            assumptions_payload_json,
            assumptions_hash,
            evaluator_version,
            metric_policy_version,
            str(horizons),
            price_basis,
            adjustment_methodology,
            adjustment_version,
            action_overlap_status,
            scoring_policy_id,
            scoring_policy_version,
            scoring_policy_hash,
            scoring_policy_status,
        ],
    )
    return run_id


def finish_evaluation_run(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
    evaluated: int,
    persisted: int,
    errors: int,
    symbol_bar_count_json: Optional[str] = None,
    benchmark_bar_count: Optional[int] = None,
    error_json: Optional[str] = None,
    status: str | None = None,
    price_basis: str = "UNKNOWN",
    adjustment_methodology: str = "UNKNOWN",
    adjustment_version: str = "UNKNOWN",
    action_overlap_status: str = "NOT_EVALUATED",
) -> None:
    """Finish an evaluation run with observed status and lineage."""
    resolved_status = status or ("FAILED" if error_json else "COMPLETE")
    conn.execute(
        """
        UPDATE outcome_evaluation_run SET
            finished_at=?,
            status=?,
            evaluated=?,
            persisted=?,
            errors=?,
            symbol_bar_count_json=?,
            benchmark_bar_count=?,
            error_json=?,
            price_basis=?,
            adjustment_methodology=?,
            adjustment_version=?,
            action_overlap_status=?
        WHERE evaluation_run_id=?
        """,
        [
            _now_utc(),
            resolved_status,
            evaluated,
            persisted,
            errors,
            symbol_bar_count_json,
            benchmark_bar_count,
            error_json,
            price_basis,
            adjustment_methodology,
            adjustment_version,
            action_overlap_status,
            run_id,
        ],
    )


def get_evaluation_run(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
) -> Optional[Dict[str, Any]]:
    """Fetch one evaluation run by ID."""
    row = conn.execute(
        """
        SELECT evaluation_run_id, watchlist_date::VARCHAR, started_at::VARCHAR,
               finished_at::VARCHAR, status, evaluator_version, metric_policy_version,
               assumptions_contract_version, assumptions_payload_json,
               assumptions_hash,
               horizons_json, symbol_bar_count_json, benchmark_bar_count,
               evaluated, persisted, errors, error_json, price_basis,
               adjustment_methodology, adjustment_version, action_overlap_status,
               scoring_policy_id, scoring_policy_version, scoring_policy_hash,
               scoring_policy_status
        FROM outcome_evaluation_run
        WHERE evaluation_run_id = ?
        """,
        [run_id],
    ).fetchone()
    if row is None:
        return None
    cols = [
        "evaluation_run_id",
        "watchlist_date",
        "started_at",
        "finished_at",
        "status",
        "evaluator_version",
        "metric_policy_version",
        "assumptions_contract_version",
        "assumptions_payload_json",
        "assumptions_hash",
        "horizons_json",
        "symbol_bar_count_json",
        "benchmark_bar_count",
        "evaluated",
        "persisted",
        "errors",
        "error_json",
        "price_basis",
        "adjustment_methodology",
        "adjustment_version",
        "action_overlap_status",
        "scoring_policy_id",
        "scoring_policy_version",
        "scoring_policy_hash",
        "scoring_policy_status",
    ]
    return dict(zip(cols, row, strict=True))


# ---- candidate_outcome ----


def upsert_candidate_outcome(
    conn: duckdb.DuckDBPyConnection, rec: CandidateOutcomeRecord
) -> None:
    """Upsert one candidate outcome row."""
    if rec.computed_at is None:
        rec.computed_at = _now_utc()
    conn.execute(
        """
        INSERT INTO candidate_outcome (
            symbol, watchlist_date, horizon_sessions,
            rank, score, candidate_class, setup_type, risk_flags_json,
            observation_start_date, observation_end_date,
            entry_close, exit_close, benchmark_entry_close, benchmark_exit_close,
            forward_return, benchmark_return, excess_return_vs_vnindex,
            max_gain, max_drawdown, hit, failure, outcome_status,
            bars_available, required_bars, computed_at, error_json,
            evaluation_run_id, evaluator_version, metric_policy_version,
            symbol_bar_count, benchmark_bar_count, price_basis,
            benchmark_price_basis, adjustment_methodology, adjustment_version,
            action_overlap_status, invalidation_reason,
            corporate_action_lineage_json, scoring_policy_id,
            scoring_policy_version, scoring_policy_hash, scoring_policy_status
        ) VALUES (
            ?,?,?,?,?,?,?,?,?,?,
            ?,?,?,?,?,?,?,?,?,?,
            ?,?,?,?,?,?,?,?,?,?,
            ?,?,?,?,?,?,?,?,?,?,?,?
        )
        ON CONFLICT (symbol, watchlist_date, horizon_sessions)
        DO UPDATE SET
            rank=excluded.rank, score=excluded.score,
            candidate_class=excluded.candidate_class,
            setup_type=excluded.setup_type,
            risk_flags_json=excluded.risk_flags_json,
            observation_start_date=excluded.observation_start_date,
            observation_end_date=excluded.observation_end_date,
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
            error_json=excluded.error_json,
            evaluation_run_id=excluded.evaluation_run_id,
            evaluator_version=excluded.evaluator_version,
            metric_policy_version=excluded.metric_policy_version,
            symbol_bar_count=excluded.symbol_bar_count,
            benchmark_bar_count=excluded.benchmark_bar_count
            ,price_basis=excluded.price_basis
            ,benchmark_price_basis=excluded.benchmark_price_basis
            ,adjustment_methodology=excluded.adjustment_methodology
            ,adjustment_version=excluded.adjustment_version
            ,action_overlap_status=excluded.action_overlap_status
            ,invalidation_reason=excluded.invalidation_reason
            ,corporate_action_lineage_json=excluded.corporate_action_lineage_json
            ,scoring_policy_id=excluded.scoring_policy_id
            ,scoring_policy_version=excluded.scoring_policy_version
            ,scoring_policy_hash=excluded.scoring_policy_hash
            ,scoring_policy_status=excluded.scoring_policy_status
        """,
        [
            rec.symbol,
            rec.watchlist_date,
            rec.horizon_sessions,
            rec.rank,
            rec.score,
            rec.candidate_class,
            rec.setup_type,
            rec.risk_flags_json,
            rec.observation_start_date,
            rec.observation_end_date,
            rec.entry_close,
            rec.exit_close,
            rec.benchmark_entry_close,
            rec.benchmark_exit_close,
            rec.forward_return,
            rec.benchmark_return,
            rec.excess_return_vs_vnindex,
            rec.max_gain,
            rec.max_drawdown,
            rec.hit,
            rec.failure,
            rec.outcome_status,
            rec.bars_available,
            rec.required_bars,
            rec.computed_at,
            rec.error_json,
            rec.evaluation_run_id,
            rec.evaluator_version,
            rec.metric_policy_version,
            rec.symbol_bar_count,
            rec.benchmark_bar_count,
            rec.price_basis,
            rec.benchmark_price_basis,
            rec.adjustment_methodology,
            rec.adjustment_version,
            rec.action_overlap_status,
            rec.invalidation_reason,
            rec.corporate_action_lineage_json,
            rec.scoring_policy_id,
            rec.scoring_policy_version,
            rec.scoring_policy_hash,
            rec.scoring_policy_status,
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
               observation_start_date::VARCHAR, observation_end_date::VARCHAR,
               entry_close, exit_close, benchmark_entry_close, benchmark_exit_close,
               forward_return, benchmark_return, excess_return_vs_vnindex,
               max_gain, max_drawdown, hit, failure, outcome_status,
               bars_available, required_bars, computed_at::VARCHAR, error_json,
               evaluation_run_id, evaluator_version, metric_policy_version,
               symbol_bar_count, benchmark_bar_count, price_basis,
               benchmark_price_basis, adjustment_methodology, adjustment_version,
               action_overlap_status, invalidation_reason,
               corporate_action_lineage_json, scoring_policy_id,
               scoring_policy_version, scoring_policy_hash, scoring_policy_status
        FROM candidate_outcome
        WHERE watchlist_date = ? AND horizon_sessions = ?
        ORDER BY score DESC NULLS LAST
        """,
        [watchlist_date, horizon_sessions],
    ).fetchall()
    cols = [
        "symbol",
        "watchlist_date",
        "horizon_sessions",
        "rank",
        "score",
        "candidate_class",
        "setup_type",
        "risk_flags_json",
        "observation_start_date",
        "observation_end_date",
        "entry_close",
        "exit_close",
        "benchmark_entry_close",
        "benchmark_exit_close",
        "forward_return",
        "benchmark_return",
        "excess_return_vs_vnindex",
        "max_gain",
        "max_drawdown",
        "hit",
        "failure",
        "outcome_status",
        "bars_available",
        "required_bars",
        "computed_at",
        "error_json",
        "evaluation_run_id",
        "evaluator_version",
        "metric_policy_version",
        "symbol_bar_count",
        "benchmark_bar_count",
        "price_basis",
        "benchmark_price_basis",
        "adjustment_methodology",
        "adjustment_version",
        "action_overlap_status",
        "invalidation_reason",
        "corporate_action_lineage_json",
        "scoring_policy_id",
        "scoring_policy_version",
        "scoring_policy_hash",
        "scoring_policy_status",
    ]
    return [dict(zip(cols, r, strict=True)) for r in rows]


def summarize_hypothesis_outcomes(
    conn: duckdb.DuckDBPyConnection,
    *,
    horizon_sessions: int,
) -> HypothesisOutcomeSummary:
    eligible_sql = feature_eligibility_sql("f")
    row = conn.execute(
        f"""
        SELECT
            count(*),
            count(*) FILTER (WHERE {eligible_sql}),
            count(o.forward_return) FILTER (
                WHERE {eligible_sql}
                  AND o.outcome_status = ?
                  AND o.price_basis = 'RAW_UNADJUSTED'
                  AND o.adjustment_methodology = 'NONE'
                  AND o.action_overlap_status = 'CLEAR'
                  AND isfinite(o.forward_return)
            ),
            avg(o.forward_return) FILTER (
                WHERE {eligible_sql}
                  AND o.outcome_status = ?
                  AND o.price_basis = 'RAW_UNADJUSTED'
                  AND o.adjustment_methodology = 'NONE'
                  AND o.action_overlap_status = 'CLEAR'
                  AND isfinite(o.forward_return)
            ),
            count(DISTINCT o.scoring_policy_hash) FILTER (
                WHERE {eligible_sql}
                  AND o.outcome_status = ?
                  AND o.price_basis = 'RAW_UNADJUSTED'
                  AND o.adjustment_methodology = 'NONE'
                  AND o.action_overlap_status = 'CLEAR'
                  AND isfinite(o.forward_return)
            ),
            min(o.scoring_policy_hash) FILTER (
                WHERE {eligible_sql}
                  AND o.outcome_status = ?
                  AND o.price_basis = 'RAW_UNADJUSTED'
                  AND o.adjustment_methodology = 'NONE'
                  AND o.action_overlap_status = 'CLEAR'
                  AND isfinite(o.forward_return)
            )
        FROM feature_snapshot f
        LEFT JOIN candidate_outcome o
          ON o.symbol = f.symbol
         AND o.watchlist_date = f.date
         AND o.horizon_sessions = ?
        WHERE f.rs_20d_vs_vnindex > 0
        """,
        [
            OutcomeStatus.COMPLETE.value,
            OutcomeStatus.COMPLETE.value,
            OutcomeStatus.COMPLETE.value,
            OutcomeStatus.COMPLETE.value,
            horizon_sessions,
        ],
    ).fetchone()
    selected = int(row[0]) if row is not None else 0
    eligible = int(row[1]) if row is not None else 0
    policy_count = int(row[4]) if row is not None else 0
    complete = int(row[2]) if row is not None and policy_count == 1 else 0
    mean_forward_return = (
        float(row[3])
        if row is not None and row[3] is not None and policy_count == 1
        else None
    )
    return HypothesisOutcomeSummary(
        selected_feature_rows=selected,
        eligible_feature_rows=eligible,
        complete_observation_rows=complete,
        excluded_feature_rows=selected - eligible,
        missing_observation_rows=eligible - complete,
        mean_forward_return=mean_forward_return,
        price_basis="RAW_UNADJUSTED" if complete else "UNKNOWN",
        adjustment_methodology="NONE" if complete else "UNKNOWN",
        adjustment_version="raw-unadjusted-v1" if complete else "UNKNOWN",
        scoring_policy_hash=(str(row[5]) if complete and row[5] is not None else None),
    )


# ---- watchlist_outcome ----


def upsert_watchlist_outcome(
    conn: duckdb.DuckDBPyConnection, rec: WatchlistOutcomeRecord
) -> None:
    if rec.computed_at is None:
        rec.computed_at = _now_utc()
    conn.execute(
        """
        INSERT INTO watchlist_outcome (
            watchlist_date, horizon_sessions,
            candidate_count, complete_count, pending_count, missing_data_count,
            invalid_count,
            avg_forward_return, median_forward_return,
            avg_excess_return, median_excess_return,
            avg_max_gain, avg_max_drawdown, hit_rate, failure_rate, computed_at,
            evaluation_run_id, evaluator_version, metric_policy_version,
            price_basis, adjustment_methodology, adjustment_version,
            action_overlap_status, scoring_policy_id, scoring_policy_version,
            scoring_policy_hash, scoring_policy_status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (watchlist_date, horizon_sessions)
        DO UPDATE SET
            candidate_count=excluded.candidate_count,
            complete_count=excluded.complete_count,
            pending_count=excluded.pending_count,
            missing_data_count=excluded.missing_data_count,
            invalid_count=excluded.invalid_count,
            avg_forward_return=excluded.avg_forward_return,
            median_forward_return=excluded.median_forward_return,
            avg_excess_return=excluded.avg_excess_return,
            median_excess_return=excluded.median_excess_return,
            avg_max_gain=excluded.avg_max_gain,
            avg_max_drawdown=excluded.avg_max_drawdown,
            hit_rate=excluded.hit_rate,
            failure_rate=excluded.failure_rate,
            computed_at=excluded.computed_at,
            evaluation_run_id=excluded.evaluation_run_id,
            evaluator_version=excluded.evaluator_version,
            metric_policy_version=excluded.metric_policy_version,
            price_basis=excluded.price_basis,
            adjustment_methodology=excluded.adjustment_methodology,
            adjustment_version=excluded.adjustment_version,
            action_overlap_status=excluded.action_overlap_status,
            scoring_policy_id=excluded.scoring_policy_id,
            scoring_policy_version=excluded.scoring_policy_version,
            scoring_policy_hash=excluded.scoring_policy_hash,
            scoring_policy_status=excluded.scoring_policy_status
        """,
        [
            rec.watchlist_date,
            rec.horizon_sessions,
            rec.candidate_count,
            rec.complete_count,
            rec.pending_count,
            rec.missing_data_count,
            rec.invalid_count,
            rec.avg_forward_return,
            rec.median_forward_return,
            rec.avg_excess_return,
            rec.median_excess_return,
            rec.avg_max_gain,
            rec.avg_max_drawdown,
            rec.hit_rate,
            rec.failure_rate,
            rec.computed_at,
            rec.evaluation_run_id,
            rec.evaluator_version,
            rec.metric_policy_version,
            rec.price_basis,
            rec.adjustment_methodology,
            rec.adjustment_version,
            rec.action_overlap_status,
            rec.scoring_policy_id,
            rec.scoring_policy_version,
            rec.scoring_policy_hash,
            rec.scoring_policy_status,
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
               complete_count, pending_count, missing_data_count, invalid_count,
               avg_forward_return, median_forward_return,
               avg_excess_return, median_excess_return,
               avg_max_gain, avg_max_drawdown, hit_rate, failure_rate,
               computed_at::VARCHAR, price_basis, adjustment_methodology,
               adjustment_version, action_overlap_status, scoring_policy_id,
               scoring_policy_version, scoring_policy_hash, scoring_policy_status
        FROM watchlist_outcome
        WHERE watchlist_date = ? AND horizon_sessions = ?
        """,
        [watchlist_date, horizon_sessions],
    ).fetchone()
    if row is None:
        return None
    cols = [
        "watchlist_date",
        "horizon_sessions",
        "candidate_count",
        "complete_count",
        "pending_count",
        "missing_data_count",
        "invalid_count",
        "avg_forward_return",
        "median_forward_return",
        "avg_excess_return",
        "median_excess_return",
        "avg_max_gain",
        "avg_max_drawdown",
        "hit_rate",
        "failure_rate",
        "computed_at",
        "price_basis",
        "adjustment_methodology",
        "adjustment_version",
        "action_overlap_status",
        "scoring_policy_id",
        "scoring_policy_version",
        "scoring_policy_hash",
        "scoring_policy_status",
    ]
    return dict(zip(cols, row, strict=True))


# ---- score_bucket_performance ----


def upsert_score_bucket_performance(
    conn: duckdb.DuckDBPyConnection, rec: ScoreBucketPerformanceRecord
) -> None:
    if rec.computed_at is None:
        rec.computed_at = _now_utc()
    conn.execute(
        """
        INSERT INTO score_bucket_performance (
            as_of_date, horizon_sessions, score_bucket,
            candidate_count, avg_forward_return, median_forward_return,
            avg_excess_return, hit_rate, failure_rate, avg_max_drawdown, computed_at,
            evaluation_run_id, evaluator_version, metric_policy_version,
            price_basis, adjustment_methodology, adjustment_version,
            action_overlap_status, scoring_policy_id, scoring_policy_version,
            scoring_policy_hash, scoring_policy_status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (as_of_date, horizon_sessions, score_bucket)
        DO UPDATE SET
            candidate_count=excluded.candidate_count,
            avg_forward_return=excluded.avg_forward_return,
            median_forward_return=excluded.median_forward_return,
            avg_excess_return=excluded.avg_excess_return,
            hit_rate=excluded.hit_rate,
            failure_rate=excluded.failure_rate,
            avg_max_drawdown=excluded.avg_max_drawdown,
            computed_at=excluded.computed_at,
            evaluation_run_id=excluded.evaluation_run_id,
            evaluator_version=excluded.evaluator_version,
            metric_policy_version=excluded.metric_policy_version,
            price_basis=excluded.price_basis,
            adjustment_methodology=excluded.adjustment_methodology,
            adjustment_version=excluded.adjustment_version,
            action_overlap_status=excluded.action_overlap_status,
            scoring_policy_id=excluded.scoring_policy_id,
            scoring_policy_version=excluded.scoring_policy_version,
            scoring_policy_hash=excluded.scoring_policy_hash,
            scoring_policy_status=excluded.scoring_policy_status
        """,
        [
            rec.as_of_date,
            rec.horizon_sessions,
            rec.score_bucket,
            rec.candidate_count,
            rec.avg_forward_return,
            rec.median_forward_return,
            rec.avg_excess_return,
            rec.hit_rate,
            rec.failure_rate,
            rec.avg_max_drawdown,
            rec.computed_at,
            rec.evaluation_run_id,
            rec.evaluator_version,
            rec.metric_policy_version,
            rec.price_basis,
            rec.adjustment_methodology,
            rec.adjustment_version,
            rec.action_overlap_status,
            rec.scoring_policy_id,
            rec.scoring_policy_version,
            rec.scoring_policy_hash,
            rec.scoring_policy_status,
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
               hit_rate, failure_rate, avg_max_drawdown, computed_at::VARCHAR,
               price_basis, adjustment_methodology, adjustment_version,
               action_overlap_status, scoring_policy_id, scoring_policy_version,
               scoring_policy_hash, scoring_policy_status
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
        "as_of_date",
        "horizon_sessions",
        "score_bucket",
        "candidate_count",
        "avg_forward_return",
        "median_forward_return",
        "avg_excess_return",
        "hit_rate",
        "failure_rate",
        "avg_max_drawdown",
        "computed_at",
        "price_basis",
        "adjustment_methodology",
        "adjustment_version",
        "action_overlap_status",
        "scoring_policy_id",
        "scoring_policy_version",
        "scoring_policy_hash",
        "scoring_policy_status",
    ]
    return [dict(zip(cols, r, strict=True)) for r in rows]


# ---- setup_type_performance ----


def upsert_setup_type_performance(
    conn: duckdb.DuckDBPyConnection, rec: SetupTypePerformanceRecord
) -> None:
    if rec.computed_at is None:
        rec.computed_at = _now_utc()
    conn.execute(
        """
        INSERT INTO setup_type_performance (
            as_of_date, horizon_sessions, setup_type,
            candidate_count, avg_forward_return, median_forward_return,
            avg_excess_return, hit_rate, failure_rate, avg_max_drawdown, computed_at,
            evaluation_run_id, evaluator_version, metric_policy_version,
            price_basis, adjustment_methodology, adjustment_version,
            action_overlap_status, scoring_policy_id, scoring_policy_version,
            scoring_policy_hash, scoring_policy_status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (as_of_date, horizon_sessions, setup_type)
        DO UPDATE SET
            candidate_count=excluded.candidate_count,
            avg_forward_return=excluded.avg_forward_return,
            median_forward_return=excluded.median_forward_return,
            avg_excess_return=excluded.avg_excess_return,
            hit_rate=excluded.hit_rate,
            failure_rate=excluded.failure_rate,
            avg_max_drawdown=excluded.avg_max_drawdown,
            computed_at=excluded.computed_at,
            evaluation_run_id=excluded.evaluation_run_id,
            evaluator_version=excluded.evaluator_version,
            metric_policy_version=excluded.metric_policy_version,
            price_basis=excluded.price_basis,
            adjustment_methodology=excluded.adjustment_methodology,
            adjustment_version=excluded.adjustment_version,
            action_overlap_status=excluded.action_overlap_status,
            scoring_policy_id=excluded.scoring_policy_id,
            scoring_policy_version=excluded.scoring_policy_version,
            scoring_policy_hash=excluded.scoring_policy_hash,
            scoring_policy_status=excluded.scoring_policy_status
        """,
        [
            rec.as_of_date,
            rec.horizon_sessions,
            rec.setup_type,
            rec.candidate_count,
            rec.avg_forward_return,
            rec.median_forward_return,
            rec.avg_excess_return,
            rec.hit_rate,
            rec.failure_rate,
            rec.avg_max_drawdown,
            rec.computed_at,
            rec.evaluation_run_id,
            rec.evaluator_version,
            rec.metric_policy_version,
            rec.price_basis,
            rec.adjustment_methodology,
            rec.adjustment_version,
            rec.action_overlap_status,
            rec.scoring_policy_id,
            rec.scoring_policy_version,
            rec.scoring_policy_hash,
            rec.scoring_policy_status,
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
               hit_rate, failure_rate, avg_max_drawdown, computed_at::VARCHAR,
               price_basis, adjustment_methodology, adjustment_version,
               action_overlap_status, scoring_policy_id, scoring_policy_version,
               scoring_policy_hash, scoring_policy_status
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
        "as_of_date",
        "horizon_sessions",
        "setup_type",
        "candidate_count",
        "avg_forward_return",
        "median_forward_return",
        "avg_excess_return",
        "hit_rate",
        "failure_rate",
        "avg_max_drawdown",
        "computed_at",
        "price_basis",
        "adjustment_methodology",
        "adjustment_version",
        "action_overlap_status",
        "scoring_policy_id",
        "scoring_policy_version",
        "scoring_policy_hash",
        "scoring_policy_status",
    ]
    return [dict(zip(cols, r, strict=True)) for r in rows]


# ---- risk_flag_performance ----


def upsert_risk_flag_performance(
    conn: duckdb.DuckDBPyConnection, rec: RiskFlagPerformanceRecord
) -> None:
    if rec.computed_at is None:
        rec.computed_at = _now_utc()
    conn.execute(
        """
        INSERT INTO risk_flag_performance (
            as_of_date, horizon_sessions, risk_flag,
            candidate_count, avg_forward_return, median_forward_return,
            avg_excess_return, hit_rate, failure_rate, avg_max_drawdown, computed_at,
            evaluation_run_id, evaluator_version, metric_policy_version,
            price_basis, adjustment_methodology, adjustment_version,
            action_overlap_status, scoring_policy_id, scoring_policy_version,
            scoring_policy_hash, scoring_policy_status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (as_of_date, horizon_sessions, risk_flag)
        DO UPDATE SET
            candidate_count=excluded.candidate_count,
            avg_forward_return=excluded.avg_forward_return,
            median_forward_return=excluded.median_forward_return,
            avg_excess_return=excluded.avg_excess_return,
            hit_rate=excluded.hit_rate,
            failure_rate=excluded.failure_rate,
            avg_max_drawdown=excluded.avg_max_drawdown,
            computed_at=excluded.computed_at,
            evaluation_run_id=excluded.evaluation_run_id,
            evaluator_version=excluded.evaluator_version,
            metric_policy_version=excluded.metric_policy_version,
            price_basis=excluded.price_basis,
            adjustment_methodology=excluded.adjustment_methodology,
            adjustment_version=excluded.adjustment_version,
            action_overlap_status=excluded.action_overlap_status,
            scoring_policy_id=excluded.scoring_policy_id,
            scoring_policy_version=excluded.scoring_policy_version,
            scoring_policy_hash=excluded.scoring_policy_hash,
            scoring_policy_status=excluded.scoring_policy_status
        """,
        [
            rec.as_of_date,
            rec.horizon_sessions,
            rec.risk_flag,
            rec.candidate_count,
            rec.avg_forward_return,
            rec.median_forward_return,
            rec.avg_excess_return,
            rec.hit_rate,
            rec.failure_rate,
            rec.avg_max_drawdown,
            rec.computed_at,
            rec.evaluation_run_id,
            rec.evaluator_version,
            rec.metric_policy_version,
            rec.price_basis,
            rec.adjustment_methodology,
            rec.adjustment_version,
            rec.action_overlap_status,
            rec.scoring_policy_id,
            rec.scoring_policy_version,
            rec.scoring_policy_hash,
            rec.scoring_policy_status,
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
               hit_rate, failure_rate, avg_max_drawdown, computed_at::VARCHAR,
               price_basis, adjustment_methodology, adjustment_version,
               action_overlap_status, scoring_policy_id, scoring_policy_version,
               scoring_policy_hash, scoring_policy_status
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
        "as_of_date",
        "horizon_sessions",
        "risk_flag",
        "candidate_count",
        "avg_forward_return",
        "median_forward_return",
        "avg_excess_return",
        "hit_rate",
        "failure_rate",
        "avg_max_drawdown",
        "computed_at",
        "price_basis",
        "adjustment_methodology",
        "adjustment_version",
        "action_overlap_status",
        "scoring_policy_id",
        "scoring_policy_version",
        "scoring_policy_hash",
        "scoring_policy_status",
    ]
    return [dict(zip(cols, r, strict=True)) for r in rows]
