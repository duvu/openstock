"""Deterministic point-in-time ranking replay engine (issue #262)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    import duckdb

REPLAY_CONTRACT_VERSION = "ranking-replay-v1"
_RAW_BASIS = "RAW_UNADJUSTED"


class ReplayContaminationError(RuntimeError):
    """Raised when a replay would consume future or incomplete data."""


@dataclass(frozen=True, slots=True)
class ReplaySpec:
    """A fixed, content-hashable historical ranking specification."""

    start_date: str
    end_date: str
    horizon_sessions: int
    top_n: int
    benchmark_symbol: str = "VNINDEX"
    cost_bps: float = 0.0
    price_basis: str = _RAW_BASIS
    scoring_policy_hash: str | None = None

    def content_hash(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ReplayPeriod:
    period_index: int
    watchlist_date: str
    selected_symbols: tuple[str, ...]
    period_excess_return: float | None
    turnover: float | None
    sector_concentration: float | None


@dataclass(frozen=True, slots=True)
class ReplayResult:
    replay_id: str
    spec_hash: str
    dataset_hash: str
    result_hash: str
    period_count: int
    total_return: float | None
    mean_period_excess: float | None
    max_drawdown: float | None
    mean_turnover: float | None
    mean_sector_concentration: float | None
    periods: list[ReplayPeriod] = field(default_factory=list)
    exclusions: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()


def _replay_dates(conn: duckdb.DuckDBPyConnection, spec: ReplaySpec) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT watchlist_date FROM candidate_outcome
        WHERE watchlist_date >= ? AND watchlist_date <= ?
          AND horizon_sessions = ?
        ORDER BY watchlist_date
        """,
        [spec.start_date, spec.end_date, spec.horizon_sessions],
    ).fetchall()
    return [str(r[0]) for r in rows]


def _period_rows(
    conn: duckdb.DuckDBPyConnection, spec: ReplaySpec, watchlist_date: str
):
    return conn.execute(
        """
        SELECT co.symbol, co.rank, co.excess_return_vs_vnindex, co.outcome_status,
               sm.sector_code
        FROM candidate_outcome co
        LEFT JOIN symbol_master sm ON sm.symbol = co.symbol
        WHERE co.watchlist_date = ? AND co.horizon_sessions = ?
          AND co.price_basis = ?
        ORDER BY co.rank
        """,
        [watchlist_date, spec.horizon_sessions, spec.price_basis],
    ).fetchall()


def run_replay(
    conn: duckdb.DuckDBPyConnection, spec: ReplaySpec, *, persist: bool = True
) -> ReplayResult:
    """Replay the fixed spec deterministically over point-in-time evidence.

    Fails closed (``ReplayContaminationError``) if any in-window ranking period
    has an outcome that is not yet mature (``COMPLETE``) for the declared
    horizon — replaying such a period would consume future or missing data.
    Identical (spec, dataset) always reproduce the same result and hashes.
    """
    dates = _replay_dates(conn, spec)
    dataset_fingerprint: list[str] = []
    periods: list[ReplayPeriod] = []
    prev_selected: set[str] = set()
    exclusions: list[str] = []

    for index, watchlist_date in enumerate(dates):
        rows = _period_rows(conn, spec, watchlist_date)
        # Contamination guard: every candidate for a replayed period must be
        # mature for the declared horizon; otherwise the period is not fully
        # observable and replaying it would use future/incomplete data.
        incomplete = [r for r in rows if r[3] != "COMPLETE"]
        if incomplete:
            raise ReplayContaminationError(
                f"period {watchlist_date} has {len(incomplete)} non-COMPLETE "
                f"outcomes for horizon {spec.horizon_sessions}; replay would "
                "consume future or incomplete data"
            )
        selected = rows[: spec.top_n]
        if not selected:
            exclusions.append(f"{watchlist_date}:no_candidates")
            continue

        symbols = tuple(r[0] for r in selected)
        excess_values = [float(r[2]) for r in selected if r[2] is not None]
        gross = sum(excess_values) / len(excess_values) if excess_values else None
        # Apply a simple round-trip cost proportional to turnover.
        current_set = set(symbols)
        entered = current_set - prev_selected
        turnover = len(entered) / len(current_set) if current_set else None
        net = gross
        if gross is not None and turnover is not None:
            net = gross - (spec.cost_bps / 10000.0) * turnover
        prev_selected = current_set

        sectors: dict[str, int] = {}
        for r in selected:
            if r[4]:
                sectors[r[4]] = sectors.get(r[4], 0) + 1
        total_sel = len(selected)
        concentration = (
            sum((c / total_sel) ** 2 for c in sectors.values()) if sectors else None
        )

        periods.append(
            ReplayPeriod(
                period_index=index,
                watchlist_date=watchlist_date,
                selected_symbols=symbols,
                period_excess_return=net,
                turnover=turnover,
                sector_concentration=concentration,
            )
        )
        dataset_fingerprint.append(
            f"{watchlist_date}|{'|'.join(f'{r[0]}:{r[2]}' for r in selected)}"
        )

    dataset_hash = hashlib.sha256(
        "\n".join(dataset_fingerprint).encode("utf-8")
    ).hexdigest()

    returns = [
        p.period_excess_return for p in periods if p.period_excess_return is not None
    ]
    total_return = sum(returns) if returns else None
    mean_excess = (sum(returns) / len(returns)) if returns else None
    max_drawdown = _max_drawdown(returns)
    turnovers = [p.turnover for p in periods if p.turnover is not None]
    mean_turnover = (sum(turnovers) / len(turnovers)) if turnovers else None
    concs = [
        p.sector_concentration for p in periods if p.sector_concentration is not None
    ]
    mean_conc = (sum(concs) / len(concs)) if concs else None

    caveats: list[str] = []
    if not periods:
        caveats.append("no_replayable_periods")

    result_payload = {
        "period_count": len(periods),
        "total_return": total_return,
        "mean_period_excess": mean_excess,
        "max_drawdown": max_drawdown,
        "periods": [
            {
                "date": p.watchlist_date,
                "symbols": list(p.selected_symbols),
                "excess": p.period_excess_return,
            }
            for p in periods
        ],
    }
    result_hash = hashlib.sha256(
        json.dumps(result_payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()

    replay = ReplayResult(
        replay_id=f"replay_{uuid4().hex[:16]}",
        spec_hash=spec.content_hash(),
        dataset_hash=dataset_hash,
        result_hash=result_hash,
        period_count=len(periods),
        total_return=total_return,
        mean_period_excess=mean_excess,
        max_drawdown=max_drawdown,
        mean_turnover=mean_turnover,
        mean_sector_concentration=mean_conc,
        periods=periods,
        exclusions=tuple(exclusions),
        caveats=tuple(caveats),
    )
    if persist:
        _persist(conn, spec, replay)
    return replay


def _max_drawdown(period_returns: list[float]) -> float | None:
    """Max peak-to-trough drawdown of the cumulative period-excess curve."""
    if not period_returns:
        return None
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in period_returns:
        cumulative += r
        peak = max(peak, cumulative)
        max_dd = min(max_dd, cumulative - peak)
    return max_dd


def _persist(
    conn: duckdb.DuckDBPyConnection, spec: ReplaySpec, result: ReplayResult
) -> None:
    existing = conn.execute(
        "SELECT replay_id FROM ranking_replay WHERE spec_hash = ? AND dataset_hash = ?",
        [result.spec_hash, result.dataset_hash],
    ).fetchone()
    if existing is not None:
        return  # immutable content-addressed artifact already present

    conn.execute(
        """
        INSERT INTO ranking_replay (
            replay_id, spec_hash, dataset_hash, result_hash,
            scoring_policy_id, scoring_policy_version, scoring_policy_hash,
            start_date, end_date, horizon_sessions, top_n, price_basis,
            benchmark_symbol, cost_bps, period_count, total_return,
            mean_period_excess, max_drawdown, mean_turnover,
            mean_sector_concentration, exclusions_json, caveats_json,
            spec_json, contract_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            result.replay_id,
            result.spec_hash,
            result.dataset_hash,
            result.result_hash,
            None,
            None,
            spec.scoring_policy_hash,
            spec.start_date,
            spec.end_date,
            spec.horizon_sessions,
            spec.top_n,
            spec.price_basis,
            spec.benchmark_symbol,
            spec.cost_bps,
            result.period_count,
            result.total_return,
            result.mean_period_excess,
            result.max_drawdown,
            result.mean_turnover,
            result.mean_sector_concentration,
            json.dumps(list(result.exclusions)),
            json.dumps(list(result.caveats)),
            json.dumps(asdict(spec), sort_keys=True),
            REPLAY_CONTRACT_VERSION,
        ],
    )
    for p in result.periods:
        conn.execute(
            """
            INSERT INTO ranking_replay_period (
                period_row_id, replay_id, period_index, watchlist_date,
                selected_count, period_excess_return, turnover,
                sector_concentration, selected_symbols_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                f"{result.replay_id}_{p.period_index}",
                result.replay_id,
                p.period_index,
                p.watchlist_date,
                len(p.selected_symbols),
                p.period_excess_return,
                p.turnover,
                p.sector_concentration,
                json.dumps(list(p.selected_symbols)),
            ],
        )
    conn.commit()


def get_replay(
    conn: duckdb.DuckDBPyConnection, replay_id: str
) -> dict[str, object] | None:
    row = conn.execute(
        """
        SELECT spec_hash, dataset_hash, result_hash, period_count, total_return,
               mean_period_excess, max_drawdown, mean_turnover,
               mean_sector_concentration, exclusions_json, caveats_json
        FROM ranking_replay WHERE replay_id = ?
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
        "period_count": row[3],
        "total_return": row[4],
        "mean_period_excess": row[5],
        "max_drawdown": row[6],
        "mean_turnover": row[7],
        "mean_sector_concentration": row[8],
        "exclusions": json.loads(row[9]) if row[9] else [],
        "caveats": json.loads(row[10]) if row[10] else [],
    }


__all__ = [
    "ReplayContaminationError",
    "ReplayPeriod",
    "ReplayResult",
    "ReplaySpec",
    "get_replay",
    "run_replay",
]
