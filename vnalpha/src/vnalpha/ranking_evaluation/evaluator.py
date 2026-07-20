"""RankingRun baseline evaluation over candidate outcomes (issue #261).

A "RankingRun" is identified by (watchlist_date, scoring_policy). This module
compares the packaged policy against momentum-only, equal-weight and unfiltered
baselines over the identical point-in-time eligible population, then persists
one immutable evaluation manifest plus per-strategy metric rows.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import uuid4

from vnalpha.ranking_evaluation.metrics import (
    hit_rate,
    mean,
    median_or_none,
    sector_concentration,
    spearman_rank_correlation,
)

if TYPE_CHECKING:
    import duckdb

RANKING_EVALUATION_CONTRACT_VERSION = "ranking-evaluation-v1"
_RAW_BASIS = "RAW_UNADJUSTED"
# Below this many complete outcomes the evaluation cannot support promotion.
MIN_SUFFICIENT_SAMPLE = 10

_ASSUMPTIONS = {
    "population": "Only COMPLETE candidate outcomes for the exact horizon and price basis.",
    "baselines": "Baselines re-rank the identical eligible population at the same cutoff.",
    "friction": "No transaction costs, slippage or capacity constraints.",
}
_ASSUMPTIONS_JSON = json.dumps(_ASSUMPTIONS, sort_keys=True, separators=(",", ":"))
_ASSUMPTIONS_HASH = hashlib.sha256(_ASSUMPTIONS_JSON.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class StrategyMetrics:
    strategy: str
    sample_count: int
    coverage: float | None
    hit_rate: float | None
    mean_excess_return: float | None
    median_excess_return: float | None
    mean_max_favorable: float | None
    mean_max_adverse: float | None
    rank_correlation: float | None
    sector_concentration: float | None


@dataclass(frozen=True, slots=True)
class RankingEvaluationResult:
    manifest_id: str
    watchlist_date: str
    horizon_sessions: int
    top_n: int
    eligible_population: int
    complete_population: int
    sufficiency_status: str
    partial_reason: str | None
    strategies: list[StrategyMetrics] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _Candidate:
    symbol: str
    rank: int
    excess_return: float
    max_gain: float | None
    max_drawdown: float | None
    momentum: float | None
    sector: str | None


def _load_population(
    conn: duckdb.DuckDBPyConnection, watchlist_date: str, horizon: int
) -> list[_Candidate]:
    rows = conn.execute(
        """
        SELECT co.symbol, co.rank, co.excess_return_vs_vnindex,
               co.max_gain, co.max_drawdown,
               fs.return_20d, sm.sector_code
        FROM candidate_outcome co
        LEFT JOIN feature_snapshot fs
               ON fs.symbol = co.symbol AND fs.date = co.watchlist_date
        LEFT JOIN symbol_master sm ON sm.symbol = co.symbol
        WHERE co.watchlist_date = ? AND co.horizon_sessions = ?
          AND co.outcome_status = 'COMPLETE'
          AND co.price_basis = ?
          AND co.excess_return_vs_vnindex IS NOT NULL
        """,
        [watchlist_date, horizon, _RAW_BASIS],
    ).fetchall()
    return [
        _Candidate(
            symbol=r[0],
            rank=int(r[1]) if r[1] is not None else 999999,
            excess_return=float(r[2]),
            max_gain=float(r[3]) if r[3] is not None else None,
            max_drawdown=float(r[4]) if r[4] is not None else None,
            momentum=float(r[5]) if r[5] is not None else None,
            sector=r[6],
        )
        for r in rows
    ]


def _metrics(strategy: str, selected: list[_Candidate], total: int) -> StrategyMetrics:
    excess = [c.excess_return for c in selected]
    gains = [c.max_gain for c in selected if c.max_gain is not None]
    draws = [c.max_drawdown for c in selected if c.max_drawdown is not None]
    sectors: dict[str, int] = {}
    for c in selected:
        if c.sector:
            sectors[c.sector] = sectors.get(c.sector, 0) + 1
    corr = spearman_rank_correlation([float(c.rank) for c in selected], excess)
    return StrategyMetrics(
        strategy=strategy,
        sample_count=len(selected),
        coverage=len(selected) / total if total else None,
        hit_rate=hit_rate(excess),
        mean_excess_return=mean(excess),
        median_excess_return=median_or_none(excess),
        mean_max_favorable=mean(gains),
        mean_max_adverse=mean(draws),
        rank_correlation=corr,
        sector_concentration=sector_concentration(sectors),
    )


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
    """Evaluate the packaged ranking against baselines over one eligible population.

    All four strategies (packaged top-N, momentum-only top-N, equal-weight
    top-N, unfiltered whole population) use the identical eligible population and
    temporal cutoff. A population smaller than ``MIN_SUFFICIENT_SAMPLE`` is
    labelled ``INSUFFICIENT`` and cannot support promotion.
    """
    population = _load_population(conn, watchlist_date, horizon)
    complete = len(population)

    if scoring_policy_hash is None and population:
        row = conn.execute(
            "SELECT scoring_policy_id, scoring_policy_version, scoring_policy_hash "
            "FROM candidate_outcome WHERE watchlist_date = ? AND horizon_sessions = ? "
            "LIMIT 1",
            [watchlist_date, horizon],
        ).fetchone()
        if row is not None:
            scoring_policy_id = scoring_policy_id or row[0]
            scoring_policy_version = scoring_policy_version or row[1]
            scoring_policy_hash = scoring_policy_hash or row[2]

    sufficiency = "SUFFICIENT" if complete >= MIN_SUFFICIENT_SAMPLE else "INSUFFICIENT"
    partial_reason = (
        None
        if sufficiency == "SUFFICIENT"
        else f"only {complete} complete outcomes (< {MIN_SUFFICIENT_SAMPLE})"
    )

    # packaged: top-N by policy rank.
    by_rank = sorted(population, key=lambda c: c.rank)
    packaged = by_rank[:top_n]
    # momentum-only: top-N by trailing return_20d (missing momentum sorts last).
    by_momentum = sorted(
        population, key=lambda c: (c.momentum is None, -(c.momentum or 0.0))
    )
    momentum = by_momentum[:top_n]
    # equal-weight: top-N by rank but treated as an equal-weight basket (metrics
    # are unweighted means, so this differs from packaged only if weighting were
    # applied; kept explicit for parity of population and cutoff).
    equal_weight = by_rank[:top_n]
    # unfiltered: the entire eligible population.
    unfiltered = population

    strategies = [
        _metrics("packaged", packaged, complete),
        _metrics("momentum_only", momentum, complete),
        _metrics("equal_weight", equal_weight, complete),
        _metrics("unfiltered", unfiltered, complete),
    ]

    manifest_id = f"rankeval_{uuid4().hex[:16]}"
    result = RankingEvaluationResult(
        manifest_id=manifest_id,
        watchlist_date=watchlist_date,
        horizon_sessions=horizon,
        top_n=top_n,
        eligible_population=complete,
        complete_population=complete,
        sufficiency_status=sufficiency,
        partial_reason=partial_reason,
        strategies=strategies,
    )

    if persist:
        _persist(
            conn,
            result,
            scoring_policy_id,
            scoring_policy_version,
            scoring_policy_hash,
        )
    return result


def _persist(
    conn: duckdb.DuckDBPyConnection,
    result: RankingEvaluationResult,
    scoring_policy_id: str | None,
    scoring_policy_version: str | None,
    scoring_policy_hash: str | None,
) -> None:
    # An evaluation manifest is immutable: never rewrite an existing one for the
    # same key (issue #261 — daily maintenance may mature inputs but not rewrite
    # prior manifests).
    existing = conn.execute(
        """
        SELECT manifest_id FROM ranking_evaluation_manifest
        WHERE watchlist_date = ? AND horizon_sessions = ? AND top_n = ?
          AND COALESCE(scoring_policy_hash, '') = COALESCE(?, '')
        """,
        [
            result.watchlist_date,
            result.horizon_sessions,
            result.top_n,
            scoring_policy_hash,
        ],
    ).fetchone()
    if existing is not None:
        return

    conn.execute(
        """
        INSERT INTO ranking_evaluation_manifest (
            manifest_id, watchlist_date, horizon_sessions, top_n, price_basis,
            scoring_policy_id, scoring_policy_version, scoring_policy_hash,
            eligible_population, complete_population, sufficiency_status,
            partial_reason, assumptions_hash, contract_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            result.manifest_id,
            result.watchlist_date,
            result.horizon_sessions,
            result.top_n,
            _RAW_BASIS,
            scoring_policy_id,
            scoring_policy_version,
            scoring_policy_hash,
            result.eligible_population,
            result.complete_population,
            result.sufficiency_status,
            result.partial_reason,
            _ASSUMPTIONS_HASH,
            RANKING_EVALUATION_CONTRACT_VERSION,
        ],
    )
    for s in result.strategies:
        conn.execute(
            """
            INSERT INTO ranking_evaluation_strategy (
                strategy_row_id, manifest_id, strategy, sample_count, coverage,
                hit_rate, mean_excess_return, median_excess_return,
                mean_max_favorable, mean_max_adverse, rank_correlation,
                turnover, sector_concentration, market_regime, metrics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                f"{result.manifest_id}_{s.strategy}",
                result.manifest_id,
                s.strategy,
                s.sample_count,
                s.coverage,
                s.hit_rate,
                s.mean_excess_return,
                s.median_excess_return,
                s.mean_max_favorable,
                s.mean_max_adverse,
                s.rank_correlation,
                None,
                s.sector_concentration,
                None,
                json.dumps(
                    {
                        "sample_count": s.sample_count,
                        "hit_rate": s.hit_rate,
                        "mean_excess_return": s.mean_excess_return,
                    },
                    sort_keys=True,
                ),
            ],
        )
    conn.commit()


def get_ranking_evaluation(
    conn: duckdb.DuckDBPyConnection, manifest_id: str
) -> dict[str, object] | None:
    manifest = conn.execute(
        """
        SELECT watchlist_date, horizon_sessions, top_n, eligible_population,
               sufficiency_status, partial_reason
        FROM ranking_evaluation_manifest WHERE manifest_id = ?
        """,
        [manifest_id],
    ).fetchone()
    if manifest is None:
        return None
    strategies = conn.execute(
        """
        SELECT strategy, sample_count, hit_rate, mean_excess_return,
               median_excess_return, rank_correlation, sector_concentration
        FROM ranking_evaluation_strategy WHERE manifest_id = ?
        ORDER BY strategy
        """,
        [manifest_id],
    ).fetchall()
    return {
        "manifest_id": manifest_id,
        "watchlist_date": str(manifest[0]),
        "horizon_sessions": manifest[1],
        "top_n": manifest[2],
        "eligible_population": manifest[3],
        "sufficiency_status": manifest[4],
        "partial_reason": manifest[5],
        "strategies": [
            {
                "strategy": s[0],
                "sample_count": s[1],
                "hit_rate": s[2],
                "mean_excess_return": s[3],
                "median_excess_return": s[4],
                "rank_correlation": s[5],
                "sector_concentration": s[6],
            }
            for s in strategies
        ],
    }


__all__ = [
    "MIN_SUFFICIENT_SAMPLE",
    "RankingEvaluationResult",
    "StrategyMetrics",
    "evaluate_ranking_run",
    "get_ranking_evaluation",
]
