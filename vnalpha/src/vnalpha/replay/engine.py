"""Deterministic point-in-time ranking replay over immutable outcome evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

from vnalpha.warehouse.point_in_time import RESOLVER_VERSION, resolve_universe

if TYPE_CHECKING:
    import duckdb

REPLAY_CONTRACT_VERSION = "ranking-replay-v2"
_RAW_BASIS = "RAW_UNADJUSTED"


class ReplayContaminationError(RuntimeError):
    """Raised when replay inputs are incomplete, mixed or future-contaminated."""


@dataclass(frozen=True, slots=True)
class ReplaySpec:
    start_date: str
    end_date: str
    horizon_sessions: int
    top_n: int
    benchmark_symbol: str = "VNINDEX"
    cost_bps: float = 0.0
    price_basis: str = _RAW_BASIS
    adjustment_version: str | None = None
    scoring_policy_hash: str | None = None
    evaluation_manifest_ids: tuple[str, ...] = ()
    rebalance_frequency: str = "EVERY_RANKING_DATE"
    holding_policy: str = "FIXED_DECLARED_HORIZON"
    liquidity_policy_version: str = "NO_LIQUIDITY_FILTER_V1"

    def content_hash(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ReplayPeriod:
    period_index: int
    watchlist_date: str
    ranking_run_ref: str
    eligible_universe_hash: str
    selected_symbols: tuple[str, ...]
    period_excess_return: float | None
    equity_value: float | None
    drawdown: float | None
    turnover: float | None
    sector_concentration: float | None
    source_outcome_hash: str


@dataclass(frozen=True, slots=True)
class ReplayResult:
    replay_id: str
    spec_hash: str
    dataset_hash: str
    result_hash: str
    scoring_policy_hash: str | None
    ranking_run_refs: tuple[str, ...]
    eligible_universe_hashes: tuple[str, ...]
    period_count: int
    total_return: float | None
    mean_period_excess: float | None
    max_drawdown: float | None
    mean_turnover: float | None
    mean_sector_concentration: float | None
    periods: list[ReplayPeriod] = field(default_factory=list)
    event_ledger: tuple[dict[str, object], ...] = ()
    exclusions: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()


def _hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _replay_dates(
    conn: duckdb.DuckDBPyConnection,
    spec: ReplaySpec,
) -> list[str]:
    query = """
        SELECT DISTINCT watchlist_date::VARCHAR
        FROM candidate_outcome
        WHERE watchlist_date >= ? AND watchlist_date <= ?
          AND horizon_sessions = ?
    """
    params: list[object] = [spec.start_date, spec.end_date, spec.horizon_sessions]
    if spec.scoring_policy_hash:
        query += " AND scoring_policy_hash = ?"
        params.append(spec.scoring_policy_hash)
    query += " ORDER BY watchlist_date"
    return [str(row[0]) for row in conn.execute(query, params).fetchall()]


def _period_rows(
    conn: duckdb.DuckDBPyConnection,
    spec: ReplaySpec,
    watchlist_date: str,
) -> list[tuple]:
    query = """
        SELECT symbol, rank, excess_return_vs_vnindex, outcome_status,
               price_basis, adjustment_version, scoring_policy_hash,
               computed_at
        FROM candidate_outcome
        WHERE watchlist_date = ? AND horizon_sessions = ?
    """
    params: list[object] = [watchlist_date, spec.horizon_sessions]
    if spec.scoring_policy_hash:
        query += " AND scoring_policy_hash = ?"
        params.append(spec.scoring_policy_hash)
    query += " ORDER BY rank NULLS LAST, symbol"
    return conn.execute(query, params).fetchall()


def _one(values: set[str], label: str) -> str:
    cleaned = {value for value in values if value}
    if len(cleaned) != 1:
        raise ReplayContaminationError(
            f"Replay requires one exact {label}; observed {sorted(cleaned)!r}"
        )
    return next(iter(cleaned))


def run_replay(
    conn: duckdb.DuckDBPyConnection,
    spec: ReplaySpec,
    *,
    persist: bool = True,
) -> ReplayResult:
    """Replay a fixed spec over exact point-in-time ranking evidence."""
    if spec.top_n < 1 or spec.horizon_sessions < 1:
        raise ValueError("top_n and horizon_sessions must be positive")
    if spec.start_date > spec.end_date:
        raise ValueError("start_date must not be after end_date")
    if spec.benchmark_symbol.upper() != "VNINDEX":
        raise ReplayContaminationError(
            "candidate_outcome stores VNINDEX-relative returns only; "
            f"benchmark {spec.benchmark_symbol!r} cannot be replayed truthfully"
        )

    dates = _replay_dates(conn, spec)
    periods: list[ReplayPeriod] = []
    exclusions: list[str] = []
    event_ledger: list[dict[str, object]] = []
    ranking_run_refs: list[str] = []
    universe_hashes: list[str] = []
    dataset_parts: list[dict[str, object]] = []
    previous_selected: set[str] | None = None
    observed_policy_hash: str | None = None
    observed_adjustment_version: str | None = spec.adjustment_version
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0

    for period_index, watchlist_date in enumerate(dates):
        rows = _period_rows(conn, spec, watchlist_date)
        if not rows:
            exclusions.append(f"{watchlist_date}:no_rows")
            continue
        incomplete = [row for row in rows if row[3] != "COMPLETE"]
        if incomplete:
            raise ReplayContaminationError(
                f"period {watchlist_date} has {len(incomplete)} non-COMPLETE "
                f"outcomes for horizon {spec.horizon_sessions}"
            )
        policy_hash = _one({str(row[6] or "") for row in rows}, "policy hash")
        basis = _one({str(row[4] or "UNKNOWN") for row in rows}, "price basis")
        adjustment_version = _one(
            {str(row[5] or "UNKNOWN") for row in rows}, "adjustment version"
        )
        if spec.scoring_policy_hash and policy_hash != spec.scoring_policy_hash:
            raise ReplayContaminationError("source policy does not match ReplaySpec")
        if basis != spec.price_basis:
            raise ReplayContaminationError(
                f"source basis {basis!r} does not match ReplaySpec {spec.price_basis!r}"
            )
        if spec.adjustment_version and adjustment_version != spec.adjustment_version:
            raise ReplayContaminationError(
                "source adjustment version does not match ReplaySpec"
            )
        if observed_policy_hash is not None and policy_hash != observed_policy_hash:
            raise ReplayContaminationError("mixed policy hashes across replay periods")
        if (
            observed_adjustment_version is not None
            and adjustment_version != observed_adjustment_version
        ):
            raise ReplayContaminationError(
                "mixed adjustment versions across replay periods"
            )
        observed_policy_hash = policy_hash
        observed_adjustment_version = adjustment_version

        universe = resolve_universe(conn, _date(watchlist_date))
        if universe.ambiguous_symbols:
            raise ReplayContaminationError(
                f"period {watchlist_date} has ambiguous point-in-time classifications: "
                f"{universe.ambiguous_symbols!r}"
            )
        candidate_symbols = {str(row[0]) for row in rows}
        missing_members = sorted(candidate_symbols - set(universe.symbols))
        if missing_members:
            raise ReplayContaminationError(
                f"period {watchlist_date} contains symbols outside the exact "
                f"point-in-time universe: {missing_members!r}"
            )

        selected = rows[: spec.top_n]
        if not selected:
            exclusions.append(f"{watchlist_date}:no_candidates")
            continue
        selected_symbols = tuple(str(row[0]) for row in selected)
        selected_set = set(selected_symbols)
        returns = [float(row[2]) for row in selected if row[2] is not None]
        if len(returns) != len(selected):
            raise ReplayContaminationError(
                f"period {watchlist_date} contains missing excess returns"
            )
        gross = sum(returns) / len(returns)
        turnover = (
            None
            if previous_selected is None
            else len(selected_set - previous_selected) / len(selected_set)
        )
        applied_turnover = 1.0 if turnover is None else turnover
        net = gross - (spec.cost_bps / 10_000.0) * applied_turnover
        previous_selected = selected_set

        sectors: dict[str, int] = {}
        for symbol in selected_symbols:
            classification = universe.get(symbol)
            if classification and classification.sector_code:
                sectors[classification.sector_code] = (
                    sectors.get(classification.sector_code, 0) + 1
                )
        concentration = (
            sum((count / len(selected_symbols)) ** 2 for count in sectors.values())
            if sectors
            else None
        )

        ranking_run_ref = f"{watchlist_date}:{policy_hash}"
        universe_payload = {
            "date": watchlist_date,
            "resolver_version": universe.resolver_version,
            "candidate_symbols": sorted(candidate_symbols),
            "classifications": {
                symbol: {
                    "sector": universe.get(symbol).sector_code,
                    "taxonomy": universe.get(symbol).taxonomy_version,
                    "snapshot": universe.get(symbol).source_snapshot_id,
                }
                for symbol in sorted(candidate_symbols)
                if universe.get(symbol) is not None
            },
        }
        universe_hash = _hash(universe_payload)
        source_payload = [
            {
                "symbol": row[0],
                "rank": row[1],
                "excess_return": row[2],
                "computed_at": str(row[7]),
                "policy_hash": row[6],
                "basis": row[4],
                "adjustment_version": row[5],
            }
            for row in rows
        ]
        source_hash = _hash(source_payload)

        equity *= 1.0 + net
        peak = max(peak, equity)
        drawdown = equity / peak - 1.0
        max_drawdown = min(max_drawdown, drawdown)
        period = ReplayPeriod(
            period_index=period_index,
            watchlist_date=watchlist_date,
            ranking_run_ref=ranking_run_ref,
            eligible_universe_hash=universe_hash,
            selected_symbols=selected_symbols,
            period_excess_return=net,
            equity_value=equity,
            drawdown=drawdown,
            turnover=turnover,
            sector_concentration=concentration,
            source_outcome_hash=source_hash,
        )
        periods.append(period)
        ranking_run_refs.append(ranking_run_ref)
        universe_hashes.append(universe_hash)
        dataset_parts.append(
            {
                "ranking_run_ref": ranking_run_ref,
                "eligible_universe_hash": universe_hash,
                "source_outcome_hash": source_hash,
                "selected_symbols": selected_symbols,
            }
        )
        event_ledger.append(
            {
                "event": "REBALANCE",
                "watchlist_date": watchlist_date,
                "selected_symbols": list(selected_symbols),
                "entered_symbols": sorted(
                    selected_set
                    if turnover is None
                    else selected_set - set(periods[-2].selected_symbols)
                ),
                "turnover": turnover,
                "cost_bps": spec.cost_bps,
            }
        )

    spec_hash = spec.content_hash()
    dataset_hash = _hash(
        {
            "spec_hash": spec_hash,
            "policy_hash": observed_policy_hash,
            "adjustment_version": observed_adjustment_version,
            "membership_resolver_version": RESOLVER_VERSION,
            "periods": dataset_parts,
            "evaluation_manifest_ids": list(spec.evaluation_manifest_ids),
        }
    )
    returns = [
        period.period_excess_return
        for period in periods
        if period.period_excess_return is not None
    ]
    total_return = equity - 1.0 if periods else None
    mean_excess = sum(returns) / len(returns) if returns else None
    turnovers = [period.turnover for period in periods if period.turnover is not None]
    concentrations = [
        period.sector_concentration
        for period in periods
        if period.sector_concentration is not None
    ]
    caveats = [] if periods else ["no_replayable_periods"]
    result_payload = {
        "spec_hash": spec_hash,
        "dataset_hash": dataset_hash,
        "policy_hash": observed_policy_hash,
        "ranking_run_refs": ranking_run_refs,
        "periods": [asdict(period) for period in periods],
        "total_return": total_return,
        "max_drawdown": max_drawdown if periods else None,
        "event_ledger": event_ledger,
    }
    result_hash = _hash(result_payload)
    replay = ReplayResult(
        replay_id=f"replay2_{result_hash[:20]}",
        spec_hash=spec_hash,
        dataset_hash=dataset_hash,
        result_hash=result_hash,
        scoring_policy_hash=observed_policy_hash,
        ranking_run_refs=tuple(ranking_run_refs),
        eligible_universe_hashes=tuple(universe_hashes),
        period_count=len(periods),
        total_return=total_return,
        mean_period_excess=mean_excess,
        max_drawdown=max_drawdown if periods else None,
        mean_turnover=(sum(turnovers) / len(turnovers)) if turnovers else None,
        mean_sector_concentration=(
            sum(concentrations) / len(concentrations) if concentrations else None
        ),
        periods=periods,
        event_ledger=tuple(event_ledger),
        exclusions=tuple(exclusions),
        caveats=tuple(caveats),
    )
    if persist:
        _persist(conn, spec, replay, observed_adjustment_version or "UNKNOWN")
    return replay


def _date(value: str):
    from datetime import date

    return date.fromisoformat(value)


def _persist(
    conn: duckdb.DuckDBPyConnection,
    spec: ReplaySpec,
    result: ReplayResult,
    adjustment_version: str,
) -> None:
    if conn.execute(
        "SELECT 1 FROM ranking_replay_v2 WHERE replay_id = ?",
        [result.replay_id],
    ).fetchone():
        return
    conn.execute(
        """
        INSERT INTO ranking_replay_v2 (
            replay_id, spec_hash, dataset_hash, result_hash,
            scoring_policy_hash, ranking_run_refs_json,
            evaluation_manifest_ids_json, eligible_universe_hashes_json,
            membership_resolver_version, start_date, end_date,
            horizon_sessions, top_n, price_basis, adjustment_version,
            benchmark_symbol, rebalance_frequency, holding_policy,
            liquidity_policy_version, cost_bps, period_count,
            compounded_total_return, mean_period_excess, max_drawdown,
            mean_turnover, mean_sector_concentration, exclusions_json,
            caveats_json, event_ledger_json, spec_json, contract_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            result.replay_id,
            result.spec_hash,
            result.dataset_hash,
            result.result_hash,
            result.scoring_policy_hash or "NO_PERIODS",
            json.dumps(list(result.ranking_run_refs)),
            json.dumps(list(spec.evaluation_manifest_ids)),
            json.dumps(list(result.eligible_universe_hashes)),
            RESOLVER_VERSION,
            spec.start_date,
            spec.end_date,
            spec.horizon_sessions,
            spec.top_n,
            spec.price_basis,
            adjustment_version,
            spec.benchmark_symbol,
            spec.rebalance_frequency,
            spec.holding_policy,
            spec.liquidity_policy_version,
            spec.cost_bps,
            result.period_count,
            result.total_return,
            result.mean_period_excess,
            result.max_drawdown,
            result.mean_turnover,
            result.mean_sector_concentration,
            json.dumps(list(result.exclusions)),
            json.dumps(list(result.caveats)),
            json.dumps(list(result.event_ledger), sort_keys=True),
            json.dumps(asdict(spec), sort_keys=True),
            REPLAY_CONTRACT_VERSION,
        ],
    )
    for period in result.periods:
        conn.execute(
            """
            INSERT INTO ranking_replay_period_v2 (
                period_row_id, replay_id, period_index, watchlist_date,
                ranking_run_ref, eligible_universe_hash, selected_count,
                period_excess_return, equity_value, drawdown, turnover,
                sector_concentration, selected_symbols_json, source_outcome_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                f"{result.replay_id}:{period.period_index}",
                result.replay_id,
                period.period_index,
                period.watchlist_date,
                period.ranking_run_ref,
                period.eligible_universe_hash,
                len(period.selected_symbols),
                period.period_excess_return,
                period.equity_value,
                period.drawdown,
                period.turnover,
                period.sector_concentration,
                json.dumps(list(period.selected_symbols)),
                period.source_outcome_hash,
            ],
        )


def get_replay(
    conn: duckdb.DuckDBPyConnection,
    replay_id: str,
) -> dict[str, object] | None:
    row = conn.execute(
        """
        SELECT spec_hash, dataset_hash, result_hash, scoring_policy_hash,
               ranking_run_refs_json, eligible_universe_hashes_json,
               membership_resolver_version, period_count,
               compounded_total_return, mean_period_excess, max_drawdown,
               mean_turnover, mean_sector_concentration, exclusions_json,
               caveats_json, event_ledger_json, contract_version
        FROM ranking_replay_v2 WHERE replay_id = ?
        """,
        [replay_id],
    ).fetchone()
    if row is None:
        return None
    return {
        "replay_id": replay_id,
        "spec_hash": row[0],
        "dataset_hash": row[1],
        "result_hash": row[2],
        "scoring_policy_hash": row[3],
        "ranking_run_refs": json.loads(row[4]),
        "eligible_universe_hashes": json.loads(row[5]),
        "membership_resolver_version": row[6],
        "period_count": row[7],
        "total_return": row[8],
        "mean_period_excess": row[9],
        "max_drawdown": row[10],
        "mean_turnover": row[11],
        "mean_sector_concentration": row[12],
        "exclusions": json.loads(row[13]),
        "caveats": json.loads(row[14]),
        "event_ledger": json.loads(row[15]),
        "contract_version": row[16],
    }


__all__ = [
    "ReplayContaminationError",
    "ReplayPeriod",
    "ReplayResult",
    "ReplaySpec",
    "get_replay",
    "run_replay",
]
