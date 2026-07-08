"""Candidate outcome evaluator for Phase 6."""

from __future__ import annotations

import importlib.metadata
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.outcomes.aggregations import aggregate_all
from vnalpha.outcomes.horizons import (
    BENCHMARK_SYMBOL,
    DEFAULT_HORIZONS,
    count_bars_available,
    get_forward_window,
    is_complete,
    select_entry_close,
    select_exit_close,
    split_bars,
)
from vnalpha.outcomes.metrics import (
    CLOSE_ONLY_V1,
    OHLC_HIGH_LOW_V1,
    classify_hit_failure,
    excess_return_vs_vnindex,
)
from vnalpha.outcomes.metrics import (
    benchmark_return as calc_benchmark_return,
)
from vnalpha.outcomes.metrics import (
    forward_return as calc_forward_return,
)
from vnalpha.outcomes.metrics import (
    max_drawdown as calc_max_drawdown,
)
from vnalpha.outcomes.metrics import (
    max_drawdown_from_lows as calc_max_drawdown_from_lows,
)
from vnalpha.outcomes.metrics import (
    max_gain as calc_max_gain,
)
from vnalpha.outcomes.metrics import (
    max_gain_from_highs as calc_max_gain_from_highs,
)
from vnalpha.outcomes.models import (
    CandidateOutcomeRecord,
    OutcomeStatus,
)
from vnalpha.outcomes.repositories import (
    create_evaluation_run,
    finish_evaluation_run,
    upsert_candidate_outcome,
)

logger = get_logger("outcomes.evaluator")

try:
    _EVALUATOR_VERSION: str = importlib.metadata.version("vnalpha")
except importlib.metadata.PackageNotFoundError:
    _EVALUATOR_VERSION = "dev"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_watchlist_rows(
    conn: duckdb.DuckDBPyConnection, watchlist_date: str
) -> List[Dict]:
    """Load daily_watchlist rows for a date.

    daily_watchlist already contains score, candidate_class, setup_type,
    risk_flags_json, lineage_json — no JOIN required.
    The table uses column 'date' (not 'watchlist_date').
    """
    rows = conn.execute(
        """
        SELECT
            symbol,
            date::VARCHAR AS watchlist_date,
            rank,
            score,
            candidate_class,
            setup_type,
            risk_flags_json,
            lineage_json
        FROM daily_watchlist
        WHERE date = ?
        ORDER BY rank ASC NULLS LAST
        """,
        [watchlist_date],
    ).fetchall()
    cols = [
        "symbol",
        "watchlist_date",
        "rank",
        "score",
        "candidate_class",
        "setup_type",
        "risk_flags_json",
        "lineage_json",
    ]
    return [dict(zip(cols, r, strict=True)) for r in rows]


def _get_ohlcv_bars(conn: duckdb.DuckDBPyConnection, symbol: str) -> List[Dict]:
    """Load canonical_ohlcv bars for a symbol, sorted ascending by time.

    Returns bars with 'time', 'close', 'high', 'low' — supporting both
    CLOSE_ONLY_V1 and OHLC_HIGH_LOW_V1 metric policies.
    """
    rows = conn.execute(
        """
        SELECT time::VARCHAR, close, high, low
        FROM canonical_ohlcv
        WHERE symbol = ? AND interval = '1D'
        ORDER BY time ASC
        """,
        [symbol],
    ).fetchall()
    bars = []
    for time_value, close, high, low in rows:
        if close is None:
            continue
        try:
            bar: Dict[str, Any] = {"time": time_value[:10], "close": float(close)}
            if high is not None:
                bar["high"] = float(high)
            if low is not None:
                bar["low"] = float(low)
            bars.append(bar)
        except (TypeError, ValueError):
            logger.warning(f"Skipping malformed bar for {symbol}: {close!r}")
    return bars


def _evaluate_single_candidate(
    conn: duckdb.DuckDBPyConnection,
    candidate: Dict[str, Any],
    horizon: int,
    symbol_bars: List[Dict],
    benchmark_bars: List[Dict],
    evaluation_run_id: Optional[str] = None,
    metric_policy: str = CLOSE_ONLY_V1,
) -> CandidateOutcomeRecord:
    symbol = candidate["symbol"]
    watchlist_date = candidate["watchlist_date"]
    computed_at = _now_utc()

    rec = CandidateOutcomeRecord(
        symbol=symbol,
        watchlist_date=watchlist_date,
        horizon_sessions=horizon,
        rank=candidate.get("rank"),
        score=candidate.get("score"),
        candidate_class=candidate.get("candidate_class"),
        setup_type=candidate.get("setup_type"),
        risk_flags_json=candidate.get("risk_flags_json"),
        required_bars=horizon,
        computed_at=computed_at,
        evaluation_run_id=evaluation_run_id,
        evaluator_version=_EVALUATOR_VERSION,
        metric_policy_version=metric_policy,
        symbol_bar_count=len(symbol_bars),
        benchmark_bar_count=len(benchmark_bars),
    )

    entry_close = select_entry_close(symbol_bars, watchlist_date)
    if entry_close is None:
        rec.outcome_status = OutcomeStatus.MISSING_DATA.value
        return rec

    rec.entry_close = entry_close
    _, future_bars = split_bars(symbol_bars, watchlist_date)
    rec.bars_available = count_bars_available(future_bars)

    if not is_complete(future_bars, horizon):
        rec.outcome_status = OutcomeStatus.PENDING.value
        return rec

    exit_close = select_exit_close(future_bars, horizon)
    rec.exit_close = exit_close

    bench_entry = select_entry_close(benchmark_bars, watchlist_date)
    _, bench_future = split_bars(benchmark_bars, watchlist_date)
    bench_exit = select_exit_close(bench_future, horizon)
    rec.benchmark_entry_close = bench_entry
    rec.benchmark_exit_close = bench_exit

    fwd = calc_forward_return(entry_close, exit_close)
    bench = calc_benchmark_return(bench_entry, bench_exit)
    excess = excess_return_vs_vnindex(fwd, bench)

    window = get_forward_window(future_bars, horizon)
    rec.forward_return = fwd
    rec.benchmark_return = bench
    rec.excess_return_vs_vnindex = excess

    if metric_policy == OHLC_HIGH_LOW_V1:
        window_highs = [b["high"] for b in window if b.get("high") is not None]
        window_lows = [b["low"] for b in window if b.get("low") is not None]
        rec.max_gain = calc_max_gain_from_highs(window_highs, entry_close)
        rec.max_drawdown = calc_max_drawdown_from_lows(window_lows, entry_close)
    else:
        window_closes = [b["close"] for b in window]
        rec.max_gain = calc_max_gain(window_closes, entry_close)
        rec.max_drawdown = calc_max_drawdown(window_closes, entry_close)

    hit, failure = classify_hit_failure(fwd, excess)
    rec.hit = hit
    rec.failure = failure

    if bench_entry is None or bench_exit is None:
        rec.outcome_status = OutcomeStatus.PARTIAL.value
    else:
        rec.outcome_status = OutcomeStatus.COMPLETE.value

    return rec


def evaluate_watchlist_date(
    conn: duckdb.DuckDBPyConnection,
    watchlist_date: str,
    horizons: Optional[List[int]] = None,
    metric_policy: str = CLOSE_ONLY_V1,
) -> Dict[str, Any]:
    if horizons is None:
        horizons = DEFAULT_HORIZONS

    candidates = _get_watchlist_rows(conn, watchlist_date)
    if not candidates:
        logger.info(f"No watchlist rows found for {watchlist_date}")
        return {
            "evaluated": 0,
            "persisted": 0,
            "errors": 0,
            "watchlist_date": watchlist_date,
            "aggregates": {},
            "evaluation_run_id": None,
        }

    run_id = create_evaluation_run(
        conn,
        watchlist_date=watchlist_date,
        evaluator_version=_EVALUATOR_VERSION,
        metric_policy_version=metric_policy,
        horizons=horizons,
    )

    benchmark_bars = _get_ohlcv_bars(conn, BENCHMARK_SYMBOL)

    persisted = 0
    errors = 0
    evaluated = 0
    symbol_bar_counts: Dict[str, int] = {}

    for candidate in candidates:
        symbol = candidate["symbol"]
        symbol_bars = _get_ohlcv_bars(conn, symbol)
        symbol_bar_counts[symbol] = len(symbol_bars)

        for horizon in horizons:
            evaluated += 1
            try:
                rec = _evaluate_single_candidate(
                    conn,
                    candidate,
                    horizon,
                    symbol_bars,
                    benchmark_bars,
                    evaluation_run_id=run_id,
                    metric_policy=metric_policy,
                )
                upsert_candidate_outcome(conn, rec)
                persisted += 1
            except Exception as exc:
                errors += 1
                logger.warning(
                    f"Error evaluating {symbol}/{watchlist_date}/h{horizon}: {exc}"
                )
                try:
                    err_rec = CandidateOutcomeRecord(
                        symbol=symbol,
                        watchlist_date=watchlist_date,
                        horizon_sessions=horizon,
                        outcome_status=OutcomeStatus.ERROR.value,
                        error_json=json.dumps({"error": str(exc)}),
                        computed_at=_now_utc(),
                        evaluation_run_id=run_id,
                        evaluator_version=_EVALUATOR_VERSION,
                        metric_policy_version=metric_policy,
                    )
                    upsert_candidate_outcome(conn, err_rec)
                except Exception:
                    pass

    aggregates: dict[int, dict[str, Any]] = {}
    for horizon in horizons:
        try:
            aggregates[horizon] = aggregate_all(
                conn,
                watchlist_date,
                horizon,
                evaluation_run_id=run_id,
                evaluator_version=_EVALUATOR_VERSION,
                metric_policy_version=metric_policy,
            )
        except Exception as exc:
            errors += 1
            logger.warning(f"Error aggregating {watchlist_date}/h{horizon}: {exc}")

    finish_evaluation_run(
        conn,
        run_id=run_id,
        evaluated=evaluated,
        persisted=persisted,
        errors=errors,
        symbol_bar_count_json=json.dumps(symbol_bar_counts),
        benchmark_bar_count=len(benchmark_bars),
    )
    try:
        from vnalpha.observability.domain import log_outcome_eval_success

        log_outcome_eval_success(
            watchlist_date, evaluated=evaluated, persisted=persisted
        )
    except Exception:  # noqa: BLE001
        pass

    logger.info(
        f"Outcome evaluation {watchlist_date}: "
        f"evaluated={evaluated}, persisted={persisted}, errors={errors}, "
        f"run_id={run_id}"
    )
    return {
        "watchlist_date": watchlist_date,
        "evaluated": evaluated,
        "persisted": persisted,
        "errors": errors,
        "aggregates": aggregates,
        "evaluation_run_id": run_id,
    }


def evaluate_date_range(
    conn: duckdb.DuckDBPyConnection,
    from_date: str,
    to_date: str,
    horizons: Optional[List[int]] = None,
    metric_policy: str = CLOSE_ONLY_V1,
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT DISTINCT date::VARCHAR
        FROM daily_watchlist
        WHERE date >= ? AND date <= ?
        ORDER BY date
        """,
        [from_date, to_date],
    ).fetchall()
    dates = [r[0] for r in rows]
    results = []
    for d in dates:
        result = evaluate_watchlist_date(
            conn, d, horizons=horizons, metric_policy=metric_policy
        )
        results.append(result)
    return results
