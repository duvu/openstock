"""Point-in-time RankingRun evaluation against distinct simple baselines."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from vnalpha.ranking_evaluation.metrics import (
    hit_rate,
    mean,
    median_or_none,
    sector_concentration,
    spearman_rank_correlation,
)
from vnalpha.warehouse.point_in_time import resolve_symbol_classification

if TYPE_CHECKING:
    import duckdb

RANKING_EVALUATION_CONTRACT_VERSION = "ranking-evaluation-v2"
MIN_SUFFICIENT_SAMPLE = 10

_ASSUMPTIONS = {
    "population": "Same-date candidate outcomes at one horizon and one exact policy/basis.",
    "packaged": "Top-N by persisted packaged rank.",
    "momentum_only": "Top-N by trailing 20-session return.",
    "equal_component": "Top-N by equal mean of available persisted score components.",
    "unfiltered": "All complete eligible outcomes.",
    "friction": "Descriptive outcome comparison; no execution or capacity claim.",
}
_ASSUMPTIONS_JSON = json.dumps(_ASSUMPTIONS, sort_keys=True, separators=(",", ":"))
_ASSUMPTIONS_HASH = hashlib.sha256(_ASSUMPTIONS_JSON.encode("utf-8")).hexdigest()


class RankingEvaluationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StrategyMetrics:
    strategy: str
    selected_symbols: tuple[str, ...]
    sample_count: int
    coverage: float | None
    hit_rate: float | None
    mean_excess_return: float | None
    median_excess_return: float | None
    mean_max_favorable: float | None
    mean_max_adverse: float | None
    rank_correlation: float | None
    turnover: float | None
    sector_concentration: float | None
    market_regime: str | None


@dataclass(frozen=True, slots=True)
class RankingEvaluationResult:
    manifest_id: str
    watchlist_date: str
    horizon_sessions: int
    top_n: int
    eligible_population: int
    complete_population: int
    incomplete_population: int
    sufficiency_status: str
    partial_reason: str | None
    scoring_policy_hash: str
    ranking_run_ref: str
    price_basis: str
    adjustment_version: str
    eligible_population_hash: str
    outcome_rows_hash: str
    dataset_hash: str
    market_regime: str | None
    strategies: list[StrategyMetrics] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _Candidate:
    symbol: str
    rank: int
    excess_return: float
    max_gain: float | None
    max_drawdown: float | None
    momentum: float | None
    equal_component_score: float | None
    sector: str | None
    computed_at: str | None
    outcome_status: str
    price_basis: str
    adjustment_version: str
    scoring_policy_id: str
    scoring_policy_version: str
    scoring_policy_hash: str


def _load_rows(
    conn: duckdb.DuckDBPyConnection,
    watchlist_date: str,
    horizon: int,
) -> list[_Candidate]:
    rows = conn.execute(
        """
        SELECT co.symbol, co.rank, co.excess_return_vs_vnindex,
               co.max_gain, co.max_drawdown, fs.return_20d,
               cs.trend_score, cs.relative_strength_score, cs.volume_score,
               cs.base_score, cs.breakout_score, cs.risk_quality_score,
               co.computed_at, co.outcome_status, co.price_basis,
               co.adjustment_version, co.scoring_policy_id,
               co.scoring_policy_version, co.scoring_policy_hash
        FROM candidate_outcome co
        LEFT JOIN feature_snapshot fs
               ON fs.symbol = co.symbol AND fs.date = co.watchlist_date
        LEFT JOIN candidate_score cs
               ON cs.symbol = co.symbol AND cs.date = co.watchlist_date
        WHERE co.watchlist_date = ? AND co.horizon_sessions = ?
        ORDER BY co.rank NULLS LAST, co.symbol
        """,
        [watchlist_date, horizon],
    ).fetchall()
    candidates: list[_Candidate] = []
    for row in rows:
        components = [float(value) for value in row[6:12] if value is not None]
        classification = resolve_symbol_classification(
            conn, str(row[0]), watchlist_date
        )
        candidates.append(
            _Candidate(
                symbol=str(row[0]),
                rank=int(row[1]) if row[1] is not None else 999_999,
                excess_return=float(row[2]) if row[2] is not None else float("nan"),
                max_gain=float(row[3]) if row[3] is not None else None,
                max_drawdown=float(row[4]) if row[4] is not None else None,
                momentum=float(row[5]) if row[5] is not None else None,
                equal_component_score=(sum(components) / len(components))
                if components
                else None,
                sector=classification.sector_code if classification else None,
                computed_at=str(row[12]) if row[12] is not None else None,
                outcome_status=str(row[13]),
                price_basis=str(row[14] or "UNKNOWN"),
                adjustment_version=str(row[15] or "UNKNOWN"),
                scoring_policy_id=str(row[16] or ""),
                scoring_policy_version=str(row[17] or ""),
                scoring_policy_hash=str(row[18] or ""),
            )
        )
    return candidates


def _one_identity(values: set[str], label: str) -> str:
    cleaned = {value for value in values if value}
    if len(cleaned) != 1:
        raise RankingEvaluationError(
            f"Evaluation requires one exact {label}; observed {sorted(cleaned)!r}"
        )
    return next(iter(cleaned))


def _content_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _select_strategies(
    candidates: list[_Candidate], top_n: int
) -> dict[str, list[_Candidate]]:
    by_rank = sorted(candidates, key=lambda item: (item.rank, item.symbol))
    by_momentum = sorted(
        candidates,
        key=lambda item: (
            item.momentum is None,
            -(item.momentum if item.momentum is not None else 0.0),
            item.symbol,
        ),
    )
    by_equal_component = sorted(
        candidates,
        key=lambda item: (
            item.equal_component_score is None,
            -(
                item.equal_component_score
                if item.equal_component_score is not None
                else 0.0
            ),
            item.symbol,
        ),
    )
    return {
        "packaged": by_rank[:top_n],
        "momentum_only": by_momentum[:top_n],
        "equal_component": by_equal_component[:top_n],
        "unfiltered": sorted(candidates, key=lambda item: item.symbol),
    }


def _previous_strategy_symbols(
    conn: duckdb.DuckDBPyConnection,
    watchlist_date: str,
    horizon: int,
    top_n: int,
    policy_hash: str,
) -> dict[str, set[str]]:
    previous = conn.execute(
        """
        SELECT MAX(watchlist_date)::VARCHAR
        FROM candidate_outcome
        WHERE watchlist_date < ? AND horizon_sessions = ?
          AND scoring_policy_hash = ?
        """,
        [watchlist_date, horizon, policy_hash],
    ).fetchone()
    if previous is None or previous[0] is None:
        return {}
    rows = _load_rows(conn, str(previous[0]), horizon)
    complete = [
        row
        for row in rows
        if row.outcome_status == "COMPLETE"
        and row.scoring_policy_hash == policy_hash
        and row.excess_return == row.excess_return
    ]
    return {
        name: {item.symbol for item in selected}
        for name, selected in _select_strategies(complete, top_n).items()
    }


def _turnover(current: set[str], previous: set[str] | None) -> float | None:
    if previous is None or not current:
        return None
    return len(current - previous) / len(current)


def _metrics(
    strategy: str,
    selected: list[_Candidate],
    total: int,
    previous: set[str] | None,
    market_regime: str | None,
) -> StrategyMetrics:
    excess = [item.excess_return for item in selected]
    gains = [item.max_gain for item in selected if item.max_gain is not None]
    draws = [item.max_drawdown for item in selected if item.max_drawdown is not None]
    sectors: dict[str, int] = {}
    for item in selected:
        if item.sector:
            sectors[item.sector] = sectors.get(item.sector, 0) + 1
    order = [float(index + 1) for index in range(len(selected))]
    symbols = tuple(item.symbol for item in selected)
    return StrategyMetrics(
        strategy=strategy,
        selected_symbols=symbols,
        sample_count=len(selected),
        coverage=len(selected) / total if total else None,
        hit_rate=hit_rate(excess),
        mean_excess_return=mean(excess),
        median_excess_return=median_or_none(excess),
        mean_max_favorable=mean(gains),
        mean_max_adverse=mean(draws),
        rank_correlation=spearman_rank_correlation(order, excess),
        turnover=_turnover(set(symbols), previous),
        sector_concentration=sector_concentration(sectors),
        market_regime=market_regime,
    )


def _market_regime(conn: duckdb.DuckDBPyConnection, watchlist_date: str) -> str | None:
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main'"
        ).fetchall()
    }
    for table in ("market_regime_snapshot", "research_market_regime_snapshot"):
        if table not in tables:
            continue
        columns = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'main' AND table_name = ?",
                [table],
            ).fetchall()
        }
        date_column = next(
            (name for name in ("as_of_date", "date") if name in columns), None
        )
        regime_column = next(
            (
                name
                for name in ("regime", "regime_label", "market_regime")
                if name in columns
            ),
            None,
        )
        if date_column and regime_column:
            row = conn.execute(
                f"SELECT {regime_column} FROM {table} WHERE {date_column} = ? LIMIT 1",
                [watchlist_date],
            ).fetchone()
            if row and row[0] is not None:
                return str(row[0])
    return None


def evaluate_ranking_run(
    conn: duckdb.DuckDBPyConnection,
    watchlist_date: str,
    *,
    horizon: int,
    top_n: int = 10,
    scoring_policy_id: str | None = None,
    scoring_policy_version: str | None = None,
    scoring_policy_hash: str | None = None,
    persist: bool = True,
) -> RankingEvaluationResult:
    if top_n < 1:
        raise ValueError("top_n must be positive")
    rows = _load_rows(conn, watchlist_date, horizon)
    if not rows:
        raise RankingEvaluationError("No candidate outcomes exist for this RankingRun")

    observed_policy_hash = _one_identity(
        {row.scoring_policy_hash for row in rows}, "scoring_policy_hash"
    )
    observed_policy_id = _one_identity(
        {row.scoring_policy_id for row in rows}, "scoring_policy_id"
    )
    observed_policy_version = _one_identity(
        {row.scoring_policy_version for row in rows}, "scoring_policy_version"
    )
    if scoring_policy_hash and scoring_policy_hash != observed_policy_hash:
        raise RankingEvaluationError("Requested policy hash does not match source rows")
    if scoring_policy_id and scoring_policy_id != observed_policy_id:
        raise RankingEvaluationError("Requested policy id does not match source rows")
    if scoring_policy_version and scoring_policy_version != observed_policy_version:
        raise RankingEvaluationError(
            "Requested policy version does not match source rows"
        )

    complete = [
        row
        for row in rows
        if row.outcome_status == "COMPLETE" and row.excess_return == row.excess_return
    ]
    incomplete_count = len(rows) - len(complete)
    if complete:
        price_basis = _one_identity(
            {row.price_basis for row in complete}, "price_basis"
        )
        adjustment_version = _one_identity(
            {row.adjustment_version for row in complete}, "adjustment_version"
        )
    else:
        price_basis = "UNKNOWN"
        adjustment_version = "UNKNOWN"

    ranking_run_ref = f"{watchlist_date}:{observed_policy_hash}"
    population_payload = [
        {
            "symbol": row.symbol,
            "rank": row.rank,
            "momentum": row.momentum,
            "equal_component_score": row.equal_component_score,
            "sector": row.sector,
        }
        for row in sorted(complete, key=lambda item: item.symbol)
    ]
    outcome_payload = [
        {
            "symbol": row.symbol,
            "excess_return": row.excess_return,
            "max_gain": row.max_gain,
            "max_drawdown": row.max_drawdown,
            "computed_at": row.computed_at,
            "basis": row.price_basis,
            "adjustment_version": row.adjustment_version,
        }
        for row in sorted(complete, key=lambda item: item.symbol)
    ]
    population_hash = _content_hash(population_payload)
    outcome_hash = _content_hash(outcome_payload)
    dataset_hash = _content_hash(
        {
            "ranking_run_ref": ranking_run_ref,
            "population_hash": population_hash,
            "outcome_hash": outcome_hash,
            "assumptions_hash": _ASSUMPTIONS_HASH,
            "horizon": horizon,
            "top_n": top_n,
        }
    )
    manifest_id = f"rankeval2_{dataset_hash[:20]}"

    if incomplete_count:
        sufficiency = "PARTIAL"
        partial_reason = f"{incomplete_count} outcome rows are not COMPLETE"
    elif len(complete) < MIN_SUFFICIENT_SAMPLE:
        sufficiency = "INSUFFICIENT"
        partial_reason = (
            f"only {len(complete)} complete outcomes (< {MIN_SUFFICIENT_SAMPLE})"
        )
    else:
        sufficiency = "SUFFICIENT"
        partial_reason = None

    selected = _select_strategies(complete, top_n)
    previous = _previous_strategy_symbols(
        conn,
        watchlist_date,
        horizon,
        top_n,
        observed_policy_hash,
    )
    regime = _market_regime(conn, watchlist_date)
    strategies = [
        _metrics(name, items, len(complete), previous.get(name), regime)
        for name, items in selected.items()
    ]
    result = RankingEvaluationResult(
        manifest_id=manifest_id,
        watchlist_date=watchlist_date,
        horizon_sessions=horizon,
        top_n=top_n,
        eligible_population=len(rows),
        complete_population=len(complete),
        incomplete_population=incomplete_count,
        sufficiency_status=sufficiency,
        partial_reason=partial_reason,
        scoring_policy_hash=observed_policy_hash,
        ranking_run_ref=ranking_run_ref,
        price_basis=price_basis,
        adjustment_version=adjustment_version,
        eligible_population_hash=population_hash,
        outcome_rows_hash=outcome_hash,
        dataset_hash=dataset_hash,
        market_regime=regime,
        strategies=strategies,
    )
    if persist:
        _persist(
            conn,
            result,
            observed_policy_id,
            observed_policy_version,
        )
    return result


def _persist(
    conn: duckdb.DuckDBPyConnection,
    result: RankingEvaluationResult,
    policy_id: str,
    policy_version: str,
) -> None:
    if conn.execute(
        "SELECT 1 FROM ranking_evaluation_manifest_v2 WHERE manifest_id = ?",
        [result.manifest_id],
    ).fetchone():
        return
    source_max = conn.execute(
        """
        SELECT MAX(computed_at) FROM candidate_outcome
        WHERE watchlist_date = ? AND horizon_sessions = ?
          AND scoring_policy_hash = ?
        """,
        [
            result.watchlist_date,
            result.horizon_sessions,
            result.scoring_policy_hash,
        ],
    ).fetchone()[0]
    conn.execute(
        """
        INSERT INTO ranking_evaluation_manifest_v2 (
            manifest_id, watchlist_date, horizon_sessions, top_n, price_basis,
            adjustment_version, scoring_policy_id, scoring_policy_version,
            scoring_policy_hash, ranking_run_ref, eligible_population,
            complete_population, incomplete_population, sufficiency_status,
            partial_reason, market_regime, assumptions_hash,
            eligible_population_hash, outcome_rows_hash, dataset_hash,
            source_max_computed_at, contract_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            result.manifest_id,
            result.watchlist_date,
            result.horizon_sessions,
            result.top_n,
            result.price_basis,
            result.adjustment_version,
            policy_id,
            policy_version,
            result.scoring_policy_hash,
            result.ranking_run_ref,
            result.eligible_population,
            result.complete_population,
            result.incomplete_population,
            result.sufficiency_status,
            result.partial_reason,
            result.market_regime,
            _ASSUMPTIONS_HASH,
            result.eligible_population_hash,
            result.outcome_rows_hash,
            result.dataset_hash,
            source_max,
            RANKING_EVALUATION_CONTRACT_VERSION,
        ],
    )
    for strategy in result.strategies:
        conn.execute(
            """
            INSERT INTO ranking_evaluation_strategy_v2 (
                strategy_row_id, manifest_id, strategy, selected_symbols_json,
                sample_count, coverage, hit_rate, mean_excess_return,
                median_excess_return, mean_max_favorable, mean_max_adverse,
                rank_correlation, turnover, sector_concentration,
                market_regime, metrics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                f"{result.manifest_id}:{strategy.strategy}",
                result.manifest_id,
                strategy.strategy,
                json.dumps(list(strategy.selected_symbols)),
                strategy.sample_count,
                strategy.coverage,
                strategy.hit_rate,
                strategy.mean_excess_return,
                strategy.median_excess_return,
                strategy.mean_max_favorable,
                strategy.mean_max_adverse,
                strategy.rank_correlation,
                strategy.turnover,
                strategy.sector_concentration,
                strategy.market_regime,
                json.dumps(
                    {
                        "sample_count": strategy.sample_count,
                        "coverage": strategy.coverage,
                        "hit_rate": strategy.hit_rate,
                        "mean_excess_return": strategy.mean_excess_return,
                        "median_excess_return": strategy.median_excess_return,
                    },
                    sort_keys=True,
                ),
            ],
        )


def get_ranking_evaluation(
    conn: duckdb.DuckDBPyConnection,
    manifest_id: str,
) -> dict[str, object] | None:
    row = conn.execute(
        """
        SELECT watchlist_date, horizon_sessions, top_n, price_basis,
               adjustment_version, scoring_policy_hash, ranking_run_ref,
               eligible_population, complete_population, incomplete_population,
               sufficiency_status, partial_reason, market_regime,
               assumptions_hash, eligible_population_hash, outcome_rows_hash,
               dataset_hash, contract_version
        FROM ranking_evaluation_manifest_v2 WHERE manifest_id = ?
        """,
        [manifest_id],
    ).fetchone()
    if row is None:
        return None
    strategies = conn.execute(
        """
        SELECT strategy, selected_symbols_json, sample_count, coverage, hit_rate,
               mean_excess_return, median_excess_return, mean_max_favorable,
               mean_max_adverse, rank_correlation, turnover,
               sector_concentration, market_regime
        FROM ranking_evaluation_strategy_v2
        WHERE manifest_id = ? ORDER BY strategy
        """,
        [manifest_id],
    ).fetchall()
    return {
        "manifest_id": manifest_id,
        "watchlist_date": str(row[0]),
        "horizon_sessions": row[1],
        "top_n": row[2],
        "price_basis": row[3],
        "adjustment_version": row[4],
        "scoring_policy_hash": row[5],
        "ranking_run_ref": row[6],
        "eligible_population": row[7],
        "complete_population": row[8],
        "incomplete_population": row[9],
        "sufficiency_status": row[10],
        "partial_reason": row[11],
        "market_regime": row[12],
        "assumptions_hash": row[13],
        "eligible_population_hash": row[14],
        "outcome_rows_hash": row[15],
        "dataset_hash": row[16],
        "contract_version": row[17],
        "strategies": [
            {
                "strategy": item[0],
                "selected_symbols": json.loads(item[1]),
                "sample_count": item[2],
                "coverage": item[3],
                "hit_rate": item[4],
                "mean_excess_return": item[5],
                "median_excess_return": item[6],
                "mean_max_favorable": item[7],
                "mean_max_adverse": item[8],
                "rank_correlation": item[9],
                "turnover": item[10],
                "sector_concentration": item[11],
                "market_regime": item[12],
            }
            for item in strategies
        ],
    }


__all__ = [
    "MIN_SUFFICIENT_SAMPLE",
    "RankingEvaluationError",
    "RankingEvaluationResult",
    "StrategyMetrics",
    "evaluate_ranking_run",
    "get_ranking_evaluation",
]
