"""Generate daily watchlist from persisted candidate scores.

Design:
- `score_universe()` computes scores from feature_snapshot and persists to candidate_score.
- `save_watchlist()` reads from candidate_score (not in-memory results) and writes daily_watchlist.
- `generate_watchlist()` runs the full pipeline: compute → persist → derive watchlist from persisted data.
"""

from __future__ import annotations

import json
from typing import List, Optional

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.scoring.score import compute_composite_score
from vnalpha.warehouse.repositories import (
    get_candidate_scores,
    save_candidate_score,
)

logger = get_logger("scoring.generate_watchlist")

DEFAULT_MIN_SCORE = 0.40
DEFAULT_TOP_N = 30

# Canonical candidate classes that qualify for the watchlist
WATCHLIST_CLASSES = {"STRONG_CANDIDATE", "WATCH_CANDIDATE", "WEAK_CANDIDATE"}


def score_universe(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    universe: Optional[List[str]] = None,
) -> int:
    """Score all symbols for a given date using feature_snapshot.

    Persists each result to candidate_score and returns the count of scored symbols.
    """
    query = """
        SELECT symbol, date, close, ma20, ma50, ma100,
               ma20_slope, ma50_slope, volume_ma20, volume_ratio,
               atr14, return_20d, return_60d, rs_20d_vs_vnindex,
               rs_60d_vs_vnindex, distance_to_ma20, distance_to_52w_high,
               base_range_30d, close_strength, volatility_20d,
               lineage_json
        FROM feature_snapshot
        WHERE date = ?
    """
    params: list = [date]
    if universe:
        placeholders = ", ".join(["?"] * len(universe))
        query += f" AND symbol IN ({placeholders})"
        params.extend(universe)

    rows = conn.execute(query, params).fetchall()
    cols = [
        "symbol",
        "date",
        "close",
        "ma20",
        "ma50",
        "ma100",
        "ma20_slope",
        "ma50_slope",
        "volume_ma20",
        "volume_ratio",
        "atr14",
        "return_20d",
        "return_60d",
        "rs_20d_vs_vnindex",
        "rs_60d_vs_vnindex",
        "distance_to_ma20",
        "distance_to_52w_high",
        "base_range_30d",
        "close_strength",
        "volatility_20d",
        "lineage_json",
    ]

    scored_count = 0
    for row in rows:
        features = dict(zip(cols, row, strict=True))
        symbol = features.pop("symbol")
        date_val = features.pop("date")
        lineage_raw = features.pop("lineage_json", None)
        # Parse feature lineage to propagate provider/ingestion_run to score
        feature_lineage: dict = {}
        if lineage_raw:
            try:
                feature_lineage = json.loads(lineage_raw)
            except (ValueError, TypeError):
                pass
        scored = compute_composite_score(features)
        scored["symbol"] = symbol
        scored["date"] = str(date_val)
        # Propagate lineage from feature_snapshot into scored result
        scored["provider"] = feature_lineage.get("provider")
        scored["ingestion_run_id"] = feature_lineage.get("ingestion_run_id")
        scored["feature_build_version"] = feature_lineage.get("feature_build_version")
        scored["as_of_bar_date"] = feature_lineage.get("as_of_bar_date")
        scored["source_quality_status"] = feature_lineage.get("source_quality_status")
        if scored.get("provider") is None:
            logger.warning(
                "Lineage: provider missing for symbol=%s date=%s — score lineage incomplete",
                symbol,
                date_val,
            )
        # Persist to candidate_score table — single authoritative record
        save_candidate_score(conn, symbol, str(date_val), scored)
        scored_count += 1

    logger.info("Scored and persisted %d symbols for %s", scored_count, date)
    return scored_count


def save_watchlist(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    top_n: int = DEFAULT_TOP_N,
    min_score: float = DEFAULT_MIN_SCORE,
) -> int:
    """Derive and save daily_watchlist FROM persisted candidate_score rows.

    Reads the authoritative candidate_score table (no recomputation) and
    writes the top-N ranked candidates to daily_watchlist.

    Returns number of entries saved.
    """
    # Read from persisted candidate_score — not in-memory scores
    candidates = get_candidate_scores(conn, date, min_score=min_score)
    # Filter to watchlist-eligible classes (IGNORE excluded)
    candidates = [
        c for c in candidates if c.get("candidate_class") in WATCHLIST_CLASSES
    ][:top_n]

    # Clear existing entries for this date
    conn.execute("DELETE FROM daily_watchlist WHERE date = ?", [date])

    for rank, candidate in enumerate(candidates, start=1):
        risk_flags = candidate.get("risk_flags_json", [])
        lineage = candidate.get("lineage_json", {})
        conn.execute(
            """
            INSERT INTO daily_watchlist
            (date, rank, symbol, score, candidate_class, setup_type, risk_flags_json, lineage_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                date,
                rank,
                candidate["symbol"],
                candidate["score"],
                candidate["candidate_class"],
                candidate["setup_type"],
                json.dumps(risk_flags) if isinstance(risk_flags, list) else risk_flags,
                json.dumps(lineage) if isinstance(lineage, dict) else lineage,
            ],
        )
    logger.info(
        "Saved %d watchlist entries for %s (from persisted scores)",
        len(candidates),
        date,
    )
    return len(candidates)


def generate_watchlist(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    universe: Optional[List[str]] = None,
    top_n: int = DEFAULT_TOP_N,
    min_score: float = DEFAULT_MIN_SCORE,
) -> dict:
    """Full pipeline: compute scores → persist → derive watchlist from persisted data.

    Returns:
        dict with "scored" count (all symbols scored) and "saved" count (watchlist entries).
    """
    try:
        from vnalpha.observability.domain import log_watchlist_start

        log_watchlist_start(date)
    except Exception:  # noqa: BLE001
        pass
    try:
        scored = score_universe(conn, date, universe=universe)
        saved = save_watchlist(conn, date, top_n=top_n, min_score=min_score)
    except Exception as exc:
        logger.error("Watchlist generation failed for %s: %s", date, exc)
        try:
            from vnalpha.observability.domain import log_watchlist_failure

            log_watchlist_failure(date, exc=exc)
        except Exception:  # noqa: BLE001
            pass
        raise
    logger.info("Watchlist for %s: scored=%d saved=%d", date, scored, saved)
    try:
        from vnalpha.observability.domain import log_watchlist_success

        log_watchlist_success(date, scored=scored, saved=saved)
    except Exception:  # noqa: BLE001
        pass
    return {"scored": scored, "saved": saved}
