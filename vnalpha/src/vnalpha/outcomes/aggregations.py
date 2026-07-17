"""Aggregate outcome performance tables."""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.outcomes.models import (
    OutcomeStatus,
    RiskFlagPerformanceRecord,
    ScoreBucketPerformanceRecord,
    SetupTypePerformanceRecord,
    WatchlistOutcomeRecord,
    assign_score_bucket,
)
from vnalpha.outcomes.repositories import (
    get_candidate_outcomes,
    upsert_risk_flag_performance,
    upsert_score_bucket_performance,
    upsert_setup_type_performance,
    upsert_watchlist_outcome,
)

logger = get_logger("outcomes.aggregations")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _safe_median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return statistics.median(values)


def _safe_rate(count: int, total: int) -> Optional[float]:
    if total == 0:
        return None
    return count / total


def _performance_lineage(row: List) -> Dict[str, Any]:
    return {
        "price_basis": row[5],
        "adjustment_methodology": row[6],
        "adjustment_version": row[7],
        "action_overlap_status": row[8],
        "scoring_policy_id": row[9],
        "scoring_policy_version": row[10],
        "scoring_policy_hash": row[11],
        "scoring_policy_status": row[12],
    }


def aggregate_watchlist_outcome(
    conn: duckdb.DuckDBPyConnection,
    watchlist_date: str,
    horizon: int,
    evaluation_run_id: Optional[str] = None,
    evaluator_version: Optional[str] = None,
    metric_policy_version: Optional[str] = None,
) -> WatchlistOutcomeRecord:
    rows = get_candidate_outcomes(conn, watchlist_date, horizon)

    complete = [
        r
        for r in rows
        if r["outcome_status"] == OutcomeStatus.COMPLETE.value
        and r.get("price_basis") == "RAW_UNADJUSTED"
        and r.get("adjustment_methodology") == "NONE"
        and r.get("action_overlap_status") == "CLEAR"
        and r.get("scoring_policy_hash") not in (None, "")
    ]
    pending = [r for r in rows if r["outcome_status"] == OutcomeStatus.PENDING.value]
    missing = [
        r
        for r in rows
        if r["outcome_status"]
        in (
            OutcomeStatus.MISSING_DATA.value,
            OutcomeStatus.PARTIAL.value,
            OutcomeStatus.ERROR.value,
        )
    ]
    invalid = [
        r
        for r in rows
        if r["outcome_status"] == OutcomeStatus.INVALID.value
        or (r["outcome_status"] == OutcomeStatus.COMPLETE.value and r not in complete)
    ]

    fwd_returns = [
        r["forward_return"] for r in complete if r["forward_return"] is not None
    ]
    excess_returns = [
        r["excess_return_vs_vnindex"]
        for r in complete
        if r["excess_return_vs_vnindex"] is not None
    ]
    max_gains = [r["max_gain"] for r in complete if r["max_gain"] is not None]
    max_dds = [r["max_drawdown"] for r in complete if r["max_drawdown"] is not None]
    hits = [r["hit"] for r in complete if r["hit"] is not None]
    failures = [r["failure"] for r in complete if r["failure"] is not None]

    rec = WatchlistOutcomeRecord(
        watchlist_date=watchlist_date,
        horizon_sessions=horizon,
        candidate_count=len(rows),
        complete_count=len(complete),
        pending_count=len(pending),
        missing_data_count=len(missing),
        invalid_count=len(invalid),
        avg_forward_return=_safe_mean(fwd_returns),
        median_forward_return=_safe_median(fwd_returns),
        avg_excess_return=_safe_mean(excess_returns),
        median_excess_return=_safe_median(excess_returns),
        avg_max_gain=_safe_mean(max_gains),
        avg_max_drawdown=_safe_mean(max_dds),
        hit_rate=_safe_rate(sum(1 for h in hits if h), len(hits)),
        failure_rate=_safe_rate(sum(1 for f in failures if f), len(failures)),
        computed_at=_now_utc(),
        evaluation_run_id=evaluation_run_id,
        evaluator_version=evaluator_version,
        metric_policy_version=metric_policy_version,
        price_basis=(complete[0]["price_basis"] if complete else "UNKNOWN"),
        adjustment_methodology=(
            complete[0]["adjustment_methodology"] if complete else "UNKNOWN"
        ),
        adjustment_version=(
            (complete[0].get("adjustment_version") or "UNKNOWN")
            if complete
            else "UNKNOWN"
        ),
        action_overlap_status="CLEAR" if complete else "NOT_EVALUATED",
        scoring_policy_id=(complete[0].get("scoring_policy_id") if complete else None),
        scoring_policy_version=(
            complete[0].get("scoring_policy_version") if complete else None
        ),
        scoring_policy_hash=(
            complete[0].get("scoring_policy_hash") if complete else None
        ),
        scoring_policy_status=(
            complete[0].get("scoring_policy_status") if complete else None
        ),
    )
    upsert_watchlist_outcome(conn, rec)
    return rec


def aggregate_score_bucket_performance(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: str,
    horizon: int,
    evaluation_run_id: Optional[str] = None,
    evaluator_version: Optional[str] = None,
    metric_policy_version: Optional[str] = None,
) -> List[ScoreBucketPerformanceRecord]:
    rows = conn.execute(
        """
        SELECT score, forward_return, excess_return_vs_vnindex,
               max_drawdown, hit, failure, price_basis,
               adjustment_methodology, adjustment_version,
               action_overlap_status, scoring_policy_id,
               scoring_policy_version, scoring_policy_hash, scoring_policy_status
        FROM candidate_outcome
        WHERE horizon_sessions = ?
          AND outcome_status = 'COMPLETE'
          AND price_basis = 'RAW_UNADJUSTED'
          AND adjustment_methodology = 'NONE'
          AND action_overlap_status = 'CLEAR'
          AND scoring_policy_hash IS NOT NULL
          AND watchlist_date <= ?
        """,
        [horizon, as_of_date],
    ).fetchall()

    buckets: Dict[str, List] = {}
    for score, fwd, excess, dd, hit, failure, *lineage in rows:
        bucket = assign_score_bucket(score)
        if bucket not in buckets:
            buckets[bucket] = []
        buckets[bucket].append((fwd, excess, dd, hit, failure, *lineage))

    records = []
    for bucket, data in sorted(buckets.items()):
        fwds = [d[0] for d in data if d[0] is not None]
        excesses = [d[1] for d in data if d[1] is not None]
        dds = [d[2] for d in data if d[2] is not None]
        hits = [d[3] for d in data if d[3] is not None]
        failures = [d[4] for d in data if d[4] is not None]

        rec = ScoreBucketPerformanceRecord(
            as_of_date=as_of_date,
            horizon_sessions=horizon,
            score_bucket=bucket,
            candidate_count=len(data),
            avg_forward_return=_safe_mean(fwds),
            median_forward_return=_safe_median(fwds),
            avg_excess_return=_safe_mean(excesses),
            hit_rate=_safe_rate(sum(1 for h in hits if h), len(hits)),
            failure_rate=_safe_rate(sum(1 for f in failures if f), len(failures)),
            avg_max_drawdown=_safe_mean(dds),
            computed_at=_now_utc(),
            evaluation_run_id=evaluation_run_id,
            evaluator_version=evaluator_version,
            metric_policy_version=metric_policy_version,
            **_performance_lineage(data[0]),
        )
        upsert_score_bucket_performance(conn, rec)
        records.append(rec)
    return records


def aggregate_setup_type_performance(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: str,
    horizon: int,
    evaluation_run_id: Optional[str] = None,
    evaluator_version: Optional[str] = None,
    metric_policy_version: Optional[str] = None,
) -> List[SetupTypePerformanceRecord]:
    rows = conn.execute(
        """
        SELECT setup_type, forward_return, excess_return_vs_vnindex,
               max_drawdown, hit, failure, price_basis,
               adjustment_methodology, adjustment_version,
               action_overlap_status, scoring_policy_id,
               scoring_policy_version, scoring_policy_hash, scoring_policy_status
        FROM candidate_outcome
        WHERE horizon_sessions = ?
          AND outcome_status = 'COMPLETE'
          AND price_basis = 'RAW_UNADJUSTED'
          AND adjustment_methodology = 'NONE'
          AND action_overlap_status = 'CLEAR'
          AND scoring_policy_hash IS NOT NULL
          AND watchlist_date <= ?
          AND setup_type IS NOT NULL
        """,
        [horizon, as_of_date],
    ).fetchall()

    by_setup: Dict[str, List] = {}
    for setup, fwd, excess, dd, hit, failure, *lineage in rows:
        if setup not in by_setup:
            by_setup[setup] = []
        by_setup[setup].append((fwd, excess, dd, hit, failure, *lineage))

    records = []
    for setup, data in sorted(by_setup.items()):
        fwds = [d[0] for d in data if d[0] is not None]
        excesses = [d[1] for d in data if d[1] is not None]
        dds = [d[2] for d in data if d[2] is not None]
        hits = [d[3] for d in data if d[3] is not None]
        failures = [d[4] for d in data if d[4] is not None]

        rec = SetupTypePerformanceRecord(
            as_of_date=as_of_date,
            horizon_sessions=horizon,
            setup_type=setup,
            candidate_count=len(data),
            avg_forward_return=_safe_mean(fwds),
            median_forward_return=_safe_median(fwds),
            avg_excess_return=_safe_mean(excesses),
            hit_rate=_safe_rate(sum(1 for h in hits if h), len(hits)),
            failure_rate=_safe_rate(sum(1 for f in failures if f), len(failures)),
            avg_max_drawdown=_safe_mean(dds),
            computed_at=_now_utc(),
            evaluation_run_id=evaluation_run_id,
            evaluator_version=evaluator_version,
            metric_policy_version=metric_policy_version,
            **_performance_lineage(data[0]),
        )
        upsert_setup_type_performance(conn, rec)
        records.append(rec)
    return records


def aggregate_risk_flag_performance(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: str,
    horizon: int,
    evaluation_run_id: Optional[str] = None,
    evaluator_version: Optional[str] = None,
    metric_policy_version: Optional[str] = None,
) -> List[RiskFlagPerformanceRecord]:
    rows = conn.execute(
        """
        SELECT risk_flags_json, forward_return, excess_return_vs_vnindex,
               max_drawdown, hit, failure, price_basis,
               adjustment_methodology, adjustment_version,
               action_overlap_status, scoring_policy_id,
               scoring_policy_version, scoring_policy_hash, scoring_policy_status
        FROM candidate_outcome
        WHERE horizon_sessions = ?
          AND outcome_status = 'COMPLETE'
          AND price_basis = 'RAW_UNADJUSTED'
          AND adjustment_methodology = 'NONE'
          AND action_overlap_status = 'CLEAR'
          AND scoring_policy_hash IS NOT NULL
          AND watchlist_date <= ?
          AND risk_flags_json IS NOT NULL
        """,
        [horizon, as_of_date],
    ).fetchall()

    by_flag: Dict[str, List] = {}
    for flags_json, fwd, excess, dd, hit, failure, *lineage in rows:
        try:
            flags = json.loads(flags_json) if flags_json else []
        except Exception:
            flags = []
        for flag in flags:
            if flag not in by_flag:
                by_flag[flag] = []
            by_flag[flag].append((fwd, excess, dd, hit, failure, *lineage))

    records = []
    for flag, data in sorted(by_flag.items()):
        fwds = [d[0] for d in data if d[0] is not None]
        excesses = [d[1] for d in data if d[1] is not None]
        dds = [d[2] for d in data if d[2] is not None]
        hits = [d[3] for d in data if d[3] is not None]
        failures = [d[4] for d in data if d[4] is not None]

        rec = RiskFlagPerformanceRecord(
            as_of_date=as_of_date,
            horizon_sessions=horizon,
            risk_flag=flag,
            candidate_count=len(data),
            avg_forward_return=_safe_mean(fwds),
            median_forward_return=_safe_median(fwds),
            avg_excess_return=_safe_mean(excesses),
            hit_rate=_safe_rate(sum(1 for h in hits if h), len(hits)),
            failure_rate=_safe_rate(sum(1 for f in failures if f), len(failures)),
            avg_max_drawdown=_safe_mean(dds),
            computed_at=_now_utc(),
            evaluation_run_id=evaluation_run_id,
            evaluator_version=evaluator_version,
            metric_policy_version=metric_policy_version,
            **_performance_lineage(data[0]),
        )
        upsert_risk_flag_performance(conn, rec)
        records.append(rec)
    return records


def aggregate_all(
    conn: duckdb.DuckDBPyConnection,
    watchlist_date: str,
    horizon: int,
    evaluation_run_id: Optional[str] = None,
    evaluator_version: Optional[str] = None,
    metric_policy_version: Optional[str] = None,
) -> Dict[str, Any]:
    wl_rec = aggregate_watchlist_outcome(
        conn,
        watchlist_date,
        horizon,
        evaluation_run_id=evaluation_run_id,
        evaluator_version=evaluator_version,
        metric_policy_version=metric_policy_version,
    )
    bucket_recs = aggregate_score_bucket_performance(
        conn,
        watchlist_date,
        horizon,
        evaluation_run_id=evaluation_run_id,
        evaluator_version=evaluator_version,
        metric_policy_version=metric_policy_version,
    )
    setup_recs = aggregate_setup_type_performance(
        conn,
        watchlist_date,
        horizon,
        evaluation_run_id=evaluation_run_id,
        evaluator_version=evaluator_version,
        metric_policy_version=metric_policy_version,
    )
    flag_recs = aggregate_risk_flag_performance(
        conn,
        watchlist_date,
        horizon,
        evaluation_run_id=evaluation_run_id,
        evaluator_version=evaluator_version,
        metric_policy_version=metric_policy_version,
    )
    return {
        "watchlist_date": watchlist_date,
        "horizon": horizon,
        "watchlist_outcome": wl_rec.candidate_count,
        "score_buckets": len(bucket_recs),
        "setup_types": len(setup_recs),
        "risk_flags": len(flag_recs),
    }
