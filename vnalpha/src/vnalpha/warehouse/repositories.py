"""Warehouse repository functions."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.core.types import CANONICAL_CANDIDATE_CLASSES, CANONICAL_SETUP_TYPES
from vnalpha.research_intelligence.models import (
    MarketRegimeSnapshot,
    SectorStrengthSnapshot,
    SymbolSectorAlignment,
)
from vnalpha.warehouse.symbol_lifecycle import (
    SymbolTaxonomyAsOf,
)
from vnalpha.warehouse.symbol_lifecycle import (
    get_symbol_taxonomy_as_of as _get_symbol_taxonomy_as_of,
)

logger = get_logger("warehouse.repositories")

# Scoring engine version for lineage tracking
SCORING_VERSION = "v1.0"
MarketRegimeRow = tuple[
    str,
    str,
    str,
    float,
    float,
    float,
    float,
    float | None,
    float | None,
    float,
    int | None,
    int | None,
    int | None,
    float | None,
    float | None,
    float | None,
    float | None,
    str,
    str,
    str,
    str,
    str | None,
    str | None,
    str,
    str,
]
SectorStrengthRow = tuple[
    str,
    str,
    int,
    int,
    int,
    float,
    float,
    float,
    float,
    float,
    float,
    int,
    float,
    str,
    float,
    int,
    str,
    str | None,
    str | None,
    str,
    str,
]


@dataclass(frozen=True, slots=True)
class _SerializedSectorStrengthSnapshot:
    snapshot: SectorStrengthSnapshot
    caveats_json: str
    lineage_json: str


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_ingestion_run(
    conn: duckdb.DuckDBPyConnection,
    source_service: str,
    source_endpoint: str,
    universe: Optional[str] = None,
    params: Optional[dict[str, Any]] = None,
) -> str:
    """Insert a new ingestion_run and return its ID."""
    run_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO ingestion_run (ingestion_run_id, started_at, status, source_service, source_endpoint, universe, params_json)
        VALUES (?, ?, 'RUNNING', ?, ?, ?, ?)
        """,
        [
            run_id,
            _now_utc(),
            source_service,
            source_endpoint,
            universe,
            json.dumps(params or {}),
        ],
    )
    return run_id


def finish_ingestion_run(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
    status: str = "SUCCESS",
    error: Optional[dict[str, Any]] = None,
) -> None:
    """Mark an ingestion_run as finished."""
    conn.execute(
        """
        UPDATE ingestion_run
        SET finished_at = ?, status = ?, error_json = ?
        WHERE ingestion_run_id = ?
        """,
        [_now_utc(), status, json.dumps(error) if error else None, run_id],
    )


def upsert_symbol(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    exchange: Optional[str] = None,
    name: Optional[str] = None,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
) -> None:
    """Insert or update a symbol in symbol_master."""
    conn.execute(
        """
        INSERT INTO symbol_master (symbol, exchange, name, sector, industry, is_active, last_seen_at)
        VALUES (?, ?, ?, ?, ?, TRUE, ?)
        ON CONFLICT (symbol) DO UPDATE SET
            exchange = excluded.exchange,
            name = excluded.name,
            sector = excluded.sector,
            industry = excluded.industry,
            is_active = TRUE,
            last_seen_at = excluded.last_seen_at
        """,
        [symbol, exchange, name, sector, industry, _now_utc()],
    )


def insert_raw_ohlcv(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
    symbol: str,
    records: list[dict[str, Any]],
    provider: str,
    quality_status: Optional[str] = None,
    fetched_at: Optional[str] = None,
) -> int:
    """Bulk insert raw OHLCV records. Returns inserted count."""
    inserted = 0
    for r in records:
        conn.execute(
            """
            INSERT OR IGNORE INTO market_ohlcv_raw
            (ingestion_run_id, symbol, time, interval, open, high, low, close, volume,
             provider, quality_status, fetched_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                symbol,
                r.get("time"),
                r.get("interval", "1D"),
                r.get("open"),
                r.get("high"),
                r.get("low"),
                r.get("close"),
                r.get("volume"),
                provider,
                quality_status,
                fetched_at,
                json.dumps(r),
            ],
        )
        inserted += 1
    return inserted


def get_symbols_active(conn: duckdb.DuckDBPyConnection) -> list[str]:
    """Return active common equities eligible for the default research universe."""
    rows = conn.execute(
        """
        SELECT symbol
        FROM symbol_master
        WHERE is_active = TRUE
          AND COALESCE(security_type, 'COMMON_EQUITY') = 'COMMON_EQUITY'
          AND COALESCE(lifecycle_status, 'ACTIVE') = 'ACTIVE'
        ORDER BY symbol
        """
    ).fetchall()
    return [r[0] for r in rows]


def get_symbol_taxonomy_as_of(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of: object,
) -> SymbolTaxonomyAsOf | None:
    """Return the historical lifecycle and taxonomy classification for a symbol."""

    return _get_symbol_taxonomy_as_of(conn, symbol, as_of)


def save_candidate_score(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str,
    score_result: dict[str, Any],
) -> None:
    """Upsert a candidate_score row from a compute_composite_score result dict.

    Persists full evidence, risk flags, and lineage including scoring version
    and generated timestamp for auditability.
    """
    # Persistence guard: enforce canonical ontology
    candidate_class_val = score_result.get("candidate_class")
    if candidate_class_val not in CANONICAL_CANDIDATE_CLASSES:
        raise ValueError(
            f"Cannot persist candidate_class '{candidate_class_val}'. "
            f"Must be one of {sorted(CANONICAL_CANDIDATE_CLASSES)}."
        )
    setup_type_val = score_result.get("setup_type")
    if setup_type_val is not None and setup_type_val not in CANONICAL_SETUP_TYPES:
        raise ValueError(
            f"Cannot persist setup_type '{setup_type_val}'. "
            f"Must be one of {sorted(CANONICAL_SETUP_TYPES)}."
        )
    generated_at = _now_utc().isoformat()
    evidence = {
        "trend_score": score_result.get("trend_score"),
        "relative_strength_score": score_result.get("relative_strength_score"),
        "volume_score": score_result.get("volume_score"),
        "base_score": score_result.get("base_score"),
        "breakout_score": score_result.get("breakout_score"),
        "risk_quality_score": score_result.get("risk_quality_score"),
        "rule_outcomes": score_result.get("rule_outcomes"),
    }
    provider = score_result.get("provider")
    ingestion_run_id = score_result.get("ingestion_run_id")
    # Compute lineage_status based on completeness of upstream metadata
    if provider is not None and ingestion_run_id is not None:
        lineage_status = "COMPLETE"
    elif provider is None and ingestion_run_id is None:
        lineage_status = "MISSING_PROVIDER"
    elif provider is not None and ingestion_run_id is None:
        lineage_status = "MISSING_INGESTION_RUN"
    else:
        lineage_status = "PARTIAL"
    lineage = {
        "scoring_version": SCORING_VERSION,
        "feature_build_version": score_result.get("feature_build_version"),
        "feature_date": date,
        "as_of_bar_date": score_result.get("as_of_bar_date"),
        "selected_provider": provider,
        "ingestion_run_id": ingestion_run_id,
        "source_quality_status": score_result.get("source_quality_status"),
        "lineage_status": lineage_status,
        "generated_at": generated_at,
        # legacy fields kept for backward compat
        "feature_snapshot_id": score_result.get("feature_snapshot_id"),
    }
    conn.execute(
        """
        INSERT INTO candidate_score
        (symbol, date, score, candidate_class, setup_type,
         trend_score, relative_strength_score, volume_score,
         base_score, breakout_score, risk_quality_score,
         evidence_json, risk_flags_json, lineage_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (symbol, date) DO UPDATE SET
            score = excluded.score,
            candidate_class = excluded.candidate_class,
            setup_type = excluded.setup_type,
            trend_score = excluded.trend_score,
            relative_strength_score = excluded.relative_strength_score,
            volume_score = excluded.volume_score,
            base_score = excluded.base_score,
            breakout_score = excluded.breakout_score,
            risk_quality_score = excluded.risk_quality_score,
            evidence_json = excluded.evidence_json,
            risk_flags_json = excluded.risk_flags_json,
            lineage_json = excluded.lineage_json
        """,
        [
            symbol,
            date,
            score_result.get("score"),
            score_result.get("candidate_class"),
            score_result.get("setup_type"),
            score_result.get("trend_score"),
            score_result.get("relative_strength_score"),
            score_result.get("volume_score"),
            score_result.get("base_score"),
            score_result.get("breakout_score"),
            score_result.get("risk_quality_score"),
            json.dumps(evidence),
            json.dumps(score_result.get("risk_flags", [])),
            json.dumps(lineage),
        ],
    )


def get_candidate_score(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str,
) -> Optional[dict[str, Any]]:
    """Return the persisted candidate_score for (symbol, date), or None if absent."""
    row = conn.execute(
        """
        SELECT symbol, date, score, candidate_class, setup_type,
               trend_score, relative_strength_score, volume_score,
               base_score, breakout_score, risk_quality_score,
               evidence_json, risk_flags_json, lineage_json
        FROM candidate_score WHERE symbol = ? AND date = ?
        """,
        [symbol, date],
    ).fetchone()
    if row is None:
        return None
    cols = [
        "symbol",
        "date",
        "score",
        "candidate_class",
        "setup_type",
        "trend_score",
        "relative_strength_score",
        "volume_score",
        "base_score",
        "breakout_score",
        "risk_quality_score",
        "evidence_json",
        "risk_flags_json",
        "lineage_json",
    ]
    result = dict(zip(cols, row, strict=True))
    # Normalise date to string
    if result["date"] is not None:
        result["date"] = str(result["date"])
    # Deserialise JSON fields
    for field in ("evidence_json", "risk_flags_json", "lineage_json"):
        if isinstance(result[field], str):
            result[field] = json.loads(result[field])
    return result


def get_candidate_scores(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Return all persisted candidate_scores for a date, ordered by score descending."""
    rows = conn.execute(
        """
        SELECT symbol, date, score, candidate_class, setup_type,
               trend_score, relative_strength_score, volume_score,
               base_score, breakout_score, risk_quality_score,
               evidence_json, risk_flags_json, lineage_json
        FROM candidate_score WHERE date = ? AND score >= ?
        ORDER BY score DESC
        """,
        [date, min_score],
    ).fetchall()
    cols = [
        "symbol",
        "date",
        "score",
        "candidate_class",
        "setup_type",
        "trend_score",
        "relative_strength_score",
        "volume_score",
        "base_score",
        "breakout_score",
        "risk_quality_score",
        "evidence_json",
        "risk_flags_json",
        "lineage_json",
    ]
    results = []
    for row in rows:
        record = dict(zip(cols, row, strict=True))
        if record["date"] is not None:
            record["date"] = str(record["date"])
        for field in ("evidence_json", "risk_flags_json", "lineage_json"):
            if isinstance(record[field], str):
                record[field] = json.loads(record[field])
        results.append(record)
    return results


def get_watchlist(conn: duckdb.DuckDBPyConnection, date: str) -> list[dict[str, Any]]:
    """Return the daily watchlist for a date, ordered by rank."""
    rows = conn.execute(
        """
        SELECT date, rank, symbol, score, candidate_class, setup_type, risk_flags_json, lineage_json
        FROM daily_watchlist WHERE date = ? ORDER BY rank
        """,
        [date],
    ).fetchall()
    cols = [
        "date",
        "rank",
        "symbol",
        "score",
        "candidate_class",
        "setup_type",
        "risk_flags_json",
        "lineage_json",
    ]
    return [dict(zip(cols, r, strict=True)) for r in rows]


def get_watchlist_rich(
    conn: duckdb.DuckDBPyConnection,
    date: str,
) -> list[dict[str, Any]]:
    """Return rich watchlist view joining daily_watchlist with candidate_score.

    Returns all fields required for Phase 5 review surface:
    rank, symbol, score, candidate_class, setup_type,
    evidence_json, risk_flags_json, lineage_json, data_quality_status.
    """
    rows = conn.execute(
        """
        SELECT
            dw.rank,
            dw.symbol,
            dw.score,
            dw.candidate_class,
            dw.setup_type,
            cs.evidence_json,
            dw.risk_flags_json,
            cs.lineage_json,
            COALESCE(co.quality_status, 'unknown') AS data_quality_status
        FROM daily_watchlist dw
        LEFT JOIN candidate_score cs
            ON cs.symbol = dw.symbol AND cs.date = dw.date
        LEFT JOIN (
            SELECT symbol, quality_status,
                ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC) AS rn
            FROM canonical_ohlcv
            WHERE interval = '1D'
              AND CAST(time AS DATE) <= ?
        ) co ON co.symbol = dw.symbol AND co.rn = 1
        WHERE dw.date = ?
        ORDER BY dw.rank
        """,
        [date, date],
    ).fetchall()

    cols = [
        "rank",
        "symbol",
        "score",
        "candidate_class",
        "setup_type",
        "evidence_json",
        "risk_flags_json",
        "lineage_json",
        "data_quality_status",
    ]
    results = []
    for row in rows:
        record = dict(zip(cols, row, strict=True))
        for field in ("evidence_json", "risk_flags_json", "lineage_json"):
            if isinstance(record[field], str):
                import json as _json

                record[field] = _json.loads(record[field])
        results.append(record)
    return results


def _normalize_snapshot_date(value: date | str) -> str:
    return value.isoformat() if isinstance(value, date) else value


def _deserialize_caveats(value: str | None) -> tuple[str, ...]:
    if not isinstance(value, str):
        return ()
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return ()
    if not isinstance(decoded, list):
        return ()
    return tuple(item for item in decoded if isinstance(item, str))


def _deserialize_lineage(value: str | None) -> Mapping[str, str]:
    if not isinstance(value, str):
        return {}
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(decoded, dict):
        return {}
    return {
        key: item
        for key, item in decoded.items()
        if isinstance(key, str) and isinstance(item, str)
    }


def _market_regime_from_row(row: MarketRegimeRow) -> MarketRegimeSnapshot | None:
    if row[10] is None or row[11] is None or row[12] is None:
        return None
    return MarketRegimeSnapshot(
        as_of_date=date.fromisoformat(row[0]),
        benchmark_symbol=row[1],
        benchmark_bar_date=date.fromisoformat(row[2]),
        close=row[3],
        ma20=row[4],
        ma50=row[5],
        ma50_slope=row[6],
        return20=row[7],
        return60=row[8],
        volatility20=row[9],
        breadth_active_count=row[10],
        breadth_eligible_count=row[11],
        breadth_excluded_count=row[12],
        breadth_coverage=row[13],
        pct_above_ma20=row[14],
        pct_above_ma50=row[15],
        pct_positive_return20=row[16],
        regime=row[17],
        trend=row[18],
        volatility=row[19],
        quality=row[20],
        caveats=_deserialize_caveats(row[21]),
        lineage=_deserialize_lineage(row[22]),
        methodology_version=row[23],
        generated_at=datetime.fromisoformat(row[24]),
    )


def _sector_strength_from_row(row: SectorStrengthRow) -> SectorStrengthSnapshot:
    return SectorStrengthSnapshot(
        as_of_date=date.fromisoformat(row[0]),
        sector=row[1],
        rank=row[2],
        member_count=row[3],
        eligible_count=row[4],
        median_return20=row[5],
        median_return60=row[6],
        median_rs20_vs_vnindex=row[7],
        median_rs60_vs_vnindex=row[8],
        pct_above_ma20=row[9],
        pct_above_ma50=row[10],
        leadership_count=row[11],
        score=row[12],
        rotation=row[13],
        metadata_coverage=row[14],
        unclassified_count=row[15],
        quality=row[16],
        caveats=_deserialize_caveats(row[17]),
        lineage=_deserialize_lineage(row[18]),
        methodology_version=row[19],
        generated_at=datetime.fromisoformat(row[20]),
    )


def upsert_market_regime_snapshot(
    conn: duckdb.DuckDBPyConnection, snapshot: MarketRegimeSnapshot
) -> None:
    """Upsert one market regime snapshot by its as-of date."""
    conn.execute(
        """
        INSERT INTO market_regime_snapshot (
            as_of_date, benchmark_symbol, benchmark_bar_date, close, ma20, ma50,
            ma50_slope, return20, return60, volatility20, breadth_active_count,
            breadth_eligible_count, breadth_excluded_count, breadth_coverage,
            pct_above_ma20, pct_above_ma50,
            pct_positive_return20, regime, trend, volatility, quality, caveats_json,
            lineage_json, methodology_version, generated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (as_of_date) DO UPDATE SET
            benchmark_symbol = excluded.benchmark_symbol,
            benchmark_bar_date = excluded.benchmark_bar_date,
            close = excluded.close,
            ma20 = excluded.ma20,
            ma50 = excluded.ma50,
            ma50_slope = excluded.ma50_slope,
            return20 = excluded.return20,
            return60 = excluded.return60,
            volatility20 = excluded.volatility20,
            breadth_active_count = excluded.breadth_active_count,
            breadth_eligible_count = excluded.breadth_eligible_count,
            breadth_excluded_count = excluded.breadth_excluded_count,
            breadth_coverage = excluded.breadth_coverage,
            pct_above_ma20 = excluded.pct_above_ma20,
            pct_above_ma50 = excluded.pct_above_ma50,
            pct_positive_return20 = excluded.pct_positive_return20,
            regime = excluded.regime,
            trend = excluded.trend,
            volatility = excluded.volatility,
            quality = excluded.quality,
            caveats_json = excluded.caveats_json,
            lineage_json = excluded.lineage_json,
            methodology_version = excluded.methodology_version,
            generated_at = excluded.generated_at
        """,
        [
            snapshot.as_of_date,
            snapshot.benchmark_symbol,
            snapshot.benchmark_bar_date,
            snapshot.close,
            snapshot.ma20,
            snapshot.ma50,
            snapshot.ma50_slope,
            snapshot.return20,
            snapshot.return60,
            snapshot.volatility20,
            snapshot.breadth_active_count,
            snapshot.breadth_eligible_count,
            snapshot.breadth_excluded_count,
            snapshot.breadth_coverage,
            snapshot.pct_above_ma20,
            snapshot.pct_above_ma50,
            snapshot.pct_positive_return20,
            snapshot.regime,
            snapshot.trend,
            snapshot.volatility,
            snapshot.quality,
            json.dumps(snapshot.caveats),
            json.dumps(dict(snapshot.lineage)),
            snapshot.methodology_version,
            snapshot.generated_at,
        ],
    )


def get_market_regime_as_of(
    conn: duckdb.DuckDBPyConnection, as_of_date: date | str
) -> MarketRegimeSnapshot | None:
    """Return the exact persisted market regime snapshot, if present."""
    row = conn.execute(
        """
        SELECT as_of_date::VARCHAR, benchmark_symbol, benchmark_bar_date::VARCHAR,
                close, ma20, ma50, ma50_slope, return20, return60, volatility20,
                breadth_active_count, breadth_eligible_count, breadth_excluded_count,
                breadth_coverage, pct_above_ma20, pct_above_ma50, pct_positive_return20,
                regime, trend, volatility, quality, caveats_json, lineage_json, methodology_version,
               generated_at::VARCHAR
        FROM market_regime_snapshot
        WHERE as_of_date = ?
        """,
        [_normalize_snapshot_date(as_of_date)],
    ).fetchone()
    return None if row is None else _market_regime_from_row(row)


def get_latest_market_regime(
    conn: duckdb.DuckDBPyConnection,
) -> MarketRegimeSnapshot | None:
    """Return the snapshot with the maximum persisted as-of date, if present."""
    row = conn.execute(
        """
        SELECT as_of_date::VARCHAR, benchmark_symbol, benchmark_bar_date::VARCHAR,
                close, ma20, ma50, ma50_slope, return20, return60, volatility20,
                breadth_active_count, breadth_eligible_count, breadth_excluded_count,
                breadth_coverage, pct_above_ma20, pct_above_ma50, pct_positive_return20,
                regime, trend, volatility, quality, caveats_json, lineage_json, methodology_version,
               generated_at::VARCHAR
        FROM market_regime_snapshot
        ORDER BY as_of_date DESC
        LIMIT 1
        """
    ).fetchone()
    return None if row is None else _market_regime_from_row(row)


def upsert_sector_strength_snapshots(
    conn: duckdb.DuckDBPyConnection, snapshots: Sequence[SectorStrengthSnapshot]
) -> None:
    """Upsert a collection of sector strength snapshots by date and sector."""
    for snapshot in snapshots:
        prepared = _prepare_sector_strength_snapshots(snapshot.as_of_date, (snapshot,))
        _upsert_sector_strength_snapshot(conn, prepared[0])


def replace_sector_strength_snapshots(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    snapshots: Sequence[SectorStrengthSnapshot],
    *,
    owns_transaction: bool = True,
) -> None:
    """Replace one date's snapshots, optionally owning transaction control.

    When ``owns_transaction`` is true, this function rolls back its own delete
    if any DuckDB write fails. Callers with an open transaction must pass false
    and retain responsibility for committing or rolling back that transaction.
    Date and JSON serialization preflight completes before either mode mutates.
    """
    prepared_snapshots = _prepare_sector_strength_snapshots(as_of_date, snapshots)
    if not owns_transaction:
        _replace_sector_strength_snapshots(conn, as_of_date, prepared_snapshots)
        return
    _ = conn.execute("BEGIN TRANSACTION")
    try:
        _replace_sector_strength_snapshots(conn, as_of_date, prepared_snapshots)
        _ = conn.execute("COMMIT")
    except duckdb.Error:
        _ = conn.execute("ROLLBACK")
        raise


def _replace_sector_strength_snapshots(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    snapshots: Sequence[_SerializedSectorStrengthSnapshot],
) -> None:
    _ = conn.execute(
        "DELETE FROM sector_strength_snapshot WHERE as_of_date = ?", [as_of_date]
    )
    for snapshot in snapshots:
        _upsert_sector_strength_snapshot(conn, snapshot)


def _prepare_sector_strength_snapshots(
    as_of_date: date,
    snapshots: Sequence[SectorStrengthSnapshot],
) -> tuple[_SerializedSectorStrengthSnapshot, ...]:
    prepared: list[_SerializedSectorStrengthSnapshot] = []
    for snapshot in snapshots:
        if snapshot.as_of_date != as_of_date:
            raise ValueError(
                f"Snapshot date {snapshot.as_of_date.isoformat()} does not match replacement date {as_of_date.isoformat()}."
            )
        prepared.append(
            _SerializedSectorStrengthSnapshot(
                snapshot=snapshot,
                caveats_json=json.dumps(snapshot.caveats),
                lineage_json=json.dumps(dict(snapshot.lineage)),
            )
        )
    return tuple(prepared)


def _upsert_sector_strength_snapshot(
    conn: duckdb.DuckDBPyConnection, snapshot: _SerializedSectorStrengthSnapshot
) -> None:
    _ = conn.execute(
        """
            INSERT INTO sector_strength_snapshot (
                as_of_date, sector, rank, member_count, eligible_count,
                median_return20, median_return60, median_rs20_vs_vnindex,
                median_rs60_vs_vnindex, pct_above_ma20, pct_above_ma50, leadership_count,
                score, rotation, metadata_coverage, unclassified_count, quality,
                caveats_json, lineage_json, methodology_version, generated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (as_of_date, sector) DO UPDATE SET
                rank = excluded.rank,
                member_count = excluded.member_count,
                eligible_count = excluded.eligible_count,
                median_return20 = excluded.median_return20,
                median_return60 = excluded.median_return60,
                median_rs20_vs_vnindex = excluded.median_rs20_vs_vnindex,
                median_rs60_vs_vnindex = excluded.median_rs60_vs_vnindex,
                pct_above_ma20 = excluded.pct_above_ma20,
                pct_above_ma50 = excluded.pct_above_ma50,
                leadership_count = excluded.leadership_count,
                score = excluded.score,
                rotation = excluded.rotation,
                metadata_coverage = excluded.metadata_coverage,
                unclassified_count = excluded.unclassified_count,
                quality = excluded.quality,
                caveats_json = excluded.caveats_json,
                lineage_json = excluded.lineage_json,
                methodology_version = excluded.methodology_version,
                generated_at = excluded.generated_at
            """,
        [
            snapshot.snapshot.as_of_date,
            snapshot.snapshot.sector,
            snapshot.snapshot.rank,
            snapshot.snapshot.member_count,
            snapshot.snapshot.eligible_count,
            snapshot.snapshot.median_return20,
            snapshot.snapshot.median_return60,
            snapshot.snapshot.median_rs20_vs_vnindex,
            snapshot.snapshot.median_rs60_vs_vnindex,
            snapshot.snapshot.pct_above_ma20,
            snapshot.snapshot.pct_above_ma50,
            snapshot.snapshot.leadership_count,
            snapshot.snapshot.score,
            snapshot.snapshot.rotation,
            snapshot.snapshot.metadata_coverage,
            snapshot.snapshot.unclassified_count,
            snapshot.snapshot.quality,
            snapshot.caveats_json,
            snapshot.lineage_json,
            snapshot.snapshot.methodology_version,
            snapshot.snapshot.generated_at,
        ],
    )


def _list_sector_strength(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date | str | None,
    limit: int | None,
) -> list[SectorStrengthSnapshot]:
    query = """
        SELECT as_of_date::VARCHAR, sector, rank, member_count, eligible_count,
               median_return20, median_return60, median_rs20_vs_vnindex,
               median_rs60_vs_vnindex, pct_above_ma20, pct_above_ma50, leadership_count,
               score, rotation, metadata_coverage, unclassified_count, quality,
               caveats_json, lineage_json, methodology_version, generated_at::VARCHAR
        FROM sector_strength_snapshot
    """
    params: list[str | int] = []
    if as_of_date is None:
        query += (
            " WHERE as_of_date = (SELECT MAX(as_of_date) FROM sector_strength_snapshot)"
            " AND leadership_count IS NOT NULL"
        )
    else:
        query += " WHERE as_of_date = ? AND leadership_count IS NOT NULL"
        params.append(_normalize_snapshot_date(as_of_date))
    query += " ORDER BY rank ASC, sector ASC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [_sector_strength_from_row(row) for row in rows]


def get_sector_strength_as_of(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date | str,
    limit: int | None = None,
) -> list[SectorStrengthSnapshot]:
    """Return exact-date sector snapshots ordered by rank then sector."""
    return _list_sector_strength(conn, as_of_date, limit)


def get_latest_sector_strength(
    conn: duckdb.DuckDBPyConnection,
    limit: int | None = None,
) -> list[SectorStrengthSnapshot]:
    """Return maximum-date sector snapshots ordered by rank then sector."""
    return _list_sector_strength(conn, None, limit)


def get_market_regime_snapshot(
    conn: duckdb.DuckDBPyConnection, as_of_date: date | str
) -> MarketRegimeSnapshot | None:
    """Compatibility delegator for the exact market-regime lookup."""
    return get_market_regime_as_of(conn, as_of_date)


def get_latest_market_regime_snapshot(
    conn: duckdb.DuckDBPyConnection,
) -> MarketRegimeSnapshot | None:
    """Compatibility delegator for the latest market-regime lookup."""
    return get_latest_market_regime(conn)


def list_sector_strength_snapshots(
    conn: duckdb.DuckDBPyConnection, as_of_date: date | str | None = None
) -> list[SectorStrengthSnapshot]:
    """Compatibility delegator for exact or latest sector lists."""
    if as_of_date is None:
        return get_latest_sector_strength(conn)
    return get_sector_strength_as_of(conn, as_of_date)


def get_symbol_sector_alignment(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of_date: date | str | None = None,
) -> SymbolSectorAlignment | None:
    """Return a symbol's persisted sector and exact or latest sector snapshot."""
    row: tuple[str | None] | None = conn.execute(
        "SELECT sector FROM symbol_master WHERE symbol = ?", [symbol]
    ).fetchone()
    if row is None:
        return None
    source_sector: str | None = row[0]
    sector = source_sector.strip() if source_sector is not None else ""
    if not sector:
        return SymbolSectorAlignment(symbol=symbol, sector=None, snapshot=None)
    snapshots = (
        get_latest_sector_strength(conn)
        if as_of_date is None
        else get_sector_strength_as_of(conn, as_of_date)
    )
    snapshot = next((item for item in snapshots if item.sector == sector), None)
    return SymbolSectorAlignment(symbol=symbol, sector=sector, snapshot=snapshot)
