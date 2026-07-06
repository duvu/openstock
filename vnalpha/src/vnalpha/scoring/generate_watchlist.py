"""Generate daily watchlist from scored candidates."""
from __future__ import annotations

import json
from typing import List, Optional

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.scoring.score import compute_composite_score
from vnalpha.warehouse.repositories import save_candidate_score

logger = get_logger("scoring.generate_watchlist")

DEFAULT_MIN_SCORE = 0.40
DEFAULT_TOP_N = 30


def score_universe(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    universe: Optional[List[str]] = None,
) -> List[dict]:
    """Score all symbols for a given date using feature_snapshot.

    Returns list of scored dicts sorted by score descending.
    """
    query = """
        SELECT symbol, date, close, ma20, ma50, ma100,
               ma20_slope, ma50_slope, volume_ma20, volume_ratio,
               atr14, return_20d, return_60d, rs_20d_vs_vnindex,
               rs_60d_vs_vnindex, distance_to_ma20, distance_to_52w_high,
               base_range_30d, close_strength, volatility_20d
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
        "symbol", "date", "close", "ma20", "ma50", "ma100",
        "ma20_slope", "ma50_slope", "volume_ma20", "volume_ratio",
        "atr14", "return_20d", "return_60d", "rs_20d_vs_vnindex",
        "rs_60d_vs_vnindex", "distance_to_ma20", "distance_to_52w_high",
        "base_range_30d", "close_strength", "volatility_20d",
    ]

    results = []
    for row in rows:
        features = dict(zip(cols, row, strict=True))
        symbol = features.pop("symbol")
        date_val = features.pop("date")
        scored = compute_composite_score(features)
        scored["symbol"] = symbol
        scored["date"] = str(date_val)
        # Persist to candidate_score table for full evidence trail
        save_candidate_score(conn, symbol, str(date_val), scored)
        results.append(scored)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def save_watchlist(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    candidates: List[dict],
    top_n: int = DEFAULT_TOP_N,
    min_score: float = DEFAULT_MIN_SCORE,
) -> int:
    """Save top candidates to daily_watchlist table.

    Returns number of entries saved.
    """
    filtered = [c for c in candidates if c["score"] >= min_score][:top_n]

    # Clear existing entries for this date
    conn.execute("DELETE FROM daily_watchlist WHERE date = ?", [date])

    for rank, candidate in enumerate(filtered, start=1):
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
                json.dumps(candidate.get("risk_flags", [])),
                json.dumps({
                    "trend_score": candidate["trend_score"],
                    "rs_score": candidate["relative_strength_score"],
                    "volume_score": candidate["volume_score"],
                }),
            ],
        )
    logger.info("Saved %d watchlist entries for %s", len(filtered), date)
    return len(filtered)


def generate_watchlist(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    universe: Optional[List[str]] = None,
    top_n: int = DEFAULT_TOP_N,
    min_score: float = DEFAULT_MIN_SCORE,
) -> dict:
    """Full pipeline: score → filter → save watchlist.

    Returns:
        dict with "scored", "saved" counts.
    """
    scored = score_universe(conn, date, universe=universe)
    saved = save_watchlist(conn, date, scored, top_n=top_n, min_score=min_score)
    logger.info("Watchlist for %s: scored=%d saved=%d", date, len(scored), saved)
    return {"scored": len(scored), "saved": saved}
