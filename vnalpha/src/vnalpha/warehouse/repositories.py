"""Warehouse repository functions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import duckdb

from vnalpha.core.logging import get_logger

logger = get_logger("warehouse.repositories")

# Scoring engine version for lineage tracking
SCORING_VERSION = "v1.0"


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
        try:
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
        except Exception as e:
            logger.warning(
                "Failed to insert raw OHLCV for %s at %s: %s", symbol, r.get("time"), e
            )
    return inserted


def get_symbols_active(conn: duckdb.DuckDBPyConnection) -> list[str]:
    """Return list of active symbols."""
    rows = conn.execute(
        "SELECT symbol FROM symbol_master WHERE is_active = TRUE ORDER BY symbol"
    ).fetchall()
    return [r[0] for r in rows]


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
    lineage = {
        "scoring_version": SCORING_VERSION,
        "generated_at": generated_at,
        "feature_date": date,
        "feature_snapshot_id": score_result.get("feature_snapshot_id"),
        "provider": score_result.get("provider"),
        "ingestion_run_id": score_result.get("ingestion_run_id"),
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
