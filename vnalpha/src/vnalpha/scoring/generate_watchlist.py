"""Generate daily watchlist from persisted candidate scores.

Design:
- `score_universe()` computes scores from feature_snapshot and persists to candidate_score.
- `save_watchlist()` reads from candidate_score (not in-memory results) and writes daily_watchlist.
- `generate_watchlist()` runs the full pipeline: compute → persist → derive watchlist from persisted data.
"""

from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import UTC, datetime
from datetime import date as DateType
from pathlib import Path
from typing import List, Optional

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY, resolve_scoring_policy
from vnalpha.scoring.score import compute_composite_score
from vnalpha.warehouse.repositories import (
    get_candidate_scores,
    save_candidate_score,
)
from vnalpha.warehouse.transaction import warehouse_transaction

logger = get_logger("scoring.generate_watchlist")

DEFAULT_MIN_SCORE = 0.40
DEFAULT_TOP_N = 30

# Canonical candidate classes that qualify for the watchlist
WATCHLIST_CLASSES = {"STRONG_CANDIDATE", "WATCH_CANDIDATE", "WEAK_CANDIDATE"}


def score_universe(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    universe: Optional[List[str]] = None,
    *,
    memory_root: Path | None = None,
    scoring_policy_id: str = BASELINE_SCORING_POLICY.policy_id,
    scoring_policy_version: str = BASELINE_SCORING_POLICY.version,
    rebuild_policy: bool = False,
    project_memory: bool = True,
    scoring_policy_auto: bool = False,
) -> int:
    """Score all symbols for a given date using feature_snapshot.

    Persists each result to candidate_score and returns the count of scored symbols.
    """
    relative_strength_columns = "fs.rs_20d_vs_vnindex, fs.rs_60d_vs_vnindex"
    if _relative_strength_snapshot_exists(conn):
        relative_strength_columns = """
            COALESCE((SELECT relative_return FROM relative_strength_snapshot rs
                      WHERE rs.symbol = fs.symbol AND rs.date = fs.date
                        AND rs.horizon_sessions = 20 AND rs.data_status = 'SUCCESS'
                        AND rs.benchmark_symbol = json_extract_string(fs.lineage_json, '$.benchmark_symbol')),
                     fs.rs_20d_vs_vnindex) AS rs_20d_vs_vnindex,
            COALESCE((SELECT relative_return FROM relative_strength_snapshot rs
                      WHERE rs.symbol = fs.symbol AND rs.date = fs.date
                        AND rs.horizon_sessions = 60 AND rs.data_status = 'SUCCESS'
                        AND rs.benchmark_symbol = json_extract_string(fs.lineage_json, '$.benchmark_symbol')),
                     fs.rs_60d_vs_vnindex) AS rs_60d_vs_vnindex
        """
    query = f"""
        SELECT fs.symbol, fs.date, fs.close, fs.ma20, fs.ma50, fs.ma100,
               ma20_slope, ma50_slope, volume_ma20, volume_ratio,
               atr14, return_20d, return_60d, {relative_strength_columns},
               distance_to_ma20, distance_to_52w_high,
               base_range_30d, close_strength, volatility_20d,
               lineage_json
        FROM feature_snapshot fs
        WHERE fs.date = ?
          AND fs.as_of_bar_date = fs.date
          AND fs.feature_data_status = 'EXACT_DATE'
          AND fs.feature_profile IN ('STANDARD_120', 'FULL_252')
          AND fs.neutral_completeness = 'COMPLETE'
          AND fs.relative_strength_completeness = 'COMPLETE'
    """
    params: list = [date]
    if universe is not None:
        if not universe:
            return 0
        placeholders = ", ".join(["?"] * len(universe))
        query += f" AND fs.symbol IN ({placeholders})"
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

    policy = resolve_scoring_policy(
        scoring_policy_id,
        scoring_policy_version,
        as_of_date=date,
        conn=conn,
        use_active_default=scoring_policy_auto,
    )
    _guard_policy_replay(
        conn,
        date,
        [str(row[0]) for row in rows],
        policy.payload_hash,
        allow_rebuild=rebuild_policy,
    )
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
        scored = compute_composite_score(features, policy=policy)
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
        save_candidate_score(
            conn,
            symbol,
            str(date_val),
            scored,
            allow_policy_rebuild=rebuild_policy,
        )
        if project_memory:
            _project_candidate_score_to_memory(
                conn, symbol, date_val, scored, memory_root=memory_root
            )
        scored_count += 1

    logger.info("Scored and persisted %d symbols for %s", scored_count, date)
    return scored_count


def _guard_policy_replay(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    symbols: list[str],
    policy_hash: str,
    *,
    allow_rebuild: bool,
) -> None:
    if allow_rebuild or not symbols:
        return
    placeholders = ", ".join(["?"] * len(symbols))
    rows = conn.execute(
        "SELECT symbol, scoring_policy_hash FROM candidate_score "
        f"WHERE date=? AND symbol IN ({placeholders})",
        [date, *symbols],
    ).fetchall()
    conflicts = sorted(
        str(symbol) for symbol, row_hash in rows if row_hash != policy_hash
    )
    if conflicts:
        raise ValueError(
            "Existing candidate scores have a different or legacy policy hash; "
            f"explicit rebuild is required for: {', '.join(conflicts)}"
        )


def _relative_strength_snapshot_exists(conn: duckdb.DuckDBPyConnection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name = 'relative_strength_snapshot'"
    ).fetchone()
    return row is not None


def _project_candidate_score_to_memory(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of_date: object,
    scored: dict,
    *,
    memory_root: Path | None,
) -> None:
    from vnalpha.symbol_memory.adapters import (
        CandidateScoreSnapshot,
        candidate_score_evidence,
    )
    from vnalpha.symbol_memory.compaction import SymbolMemoryCompactionService
    from vnalpha.symbol_memory.ingestion import (
        MemoryIngestionError,
        SymbolMemoryIngestionService,
    )
    from vnalpha.symbol_memory.repository import SymbolMemoryRepository

    try:
        resolved_date = DateType.fromisoformat(str(as_of_date))
        snapshot = CandidateScoreSnapshot(
            symbol=symbol,
            as_of_date=resolved_date,
            score=float(scored["score"]),
            candidate_class=str(scored["candidate_class"]),
            setup_type=(
                None if scored.get("setup_type") is None else str(scored["setup_type"])
            ),
            correlation_id=f"candidate-score:{symbol}:{resolved_date.isoformat()}",
            persisted_at=datetime.now(UTC),
            scoring_policy_id=str(scored["scoring_policy_id"]),
            scoring_policy_hash=str(scored["scoring_policy_hash"]),
        )
        repository = SymbolMemoryRepository(conn)
        ingestion = SymbolMemoryIngestionService(repository)
        SymbolMemoryCompactionService(repository, memory_root).mutate_and_compact(
            symbol,
            lambda: ingestion.ingest_evidence(candidate_score_evidence(snapshot)),
        )
    except (MemoryIngestionError, ValueError, duckdb.Error) as exc:
        logger.warning(
            "Symbol memory projection failed for symbol=%s date=%s: %s",
            symbol,
            as_of_date,
            exc,
        )


def save_watchlist(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    top_n: int = DEFAULT_TOP_N,
    min_score: float = DEFAULT_MIN_SCORE,
    *,
    scoring_policy_id: str = BASELINE_SCORING_POLICY.policy_id,
    scoring_policy_version: str = BASELINE_SCORING_POLICY.version,
    allow_policy_rebuild: bool = False,
    manage_transaction: bool = True,
    scoring_policy_auto: bool = False,
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

    policy = resolve_scoring_policy(
        scoring_policy_id,
        scoring_policy_version,
        as_of_date=date,
        conn=conn,
        use_active_default=scoring_policy_auto,
    )
    identities = {
        (
            str(c.get("scoring_policy_id") or ""),
            str(c.get("scoring_policy_version") or ""),
            str(c.get("scoring_policy_hash") or ""),
            str(c.get("scoring_policy_status") or ""),
        )
        for c in candidates
    }
    expected_identity = (
        policy.policy_id,
        policy.version,
        policy.payload_hash,
        policy.lifecycle_status.value,
    )
    if identities and identities != {expected_identity}:
        raise ValueError(
            "Watchlist candidates have missing, mixed, or invalid policy identity"
        )
    existing_identities = set(
        conn.execute(
            "SELECT DISTINCT scoring_policy_id, scoring_policy_version, "
            "scoring_policy_hash, scoring_policy_status "
            "FROM daily_watchlist WHERE date=?",
            [date],
        ).fetchall()
    )
    if (
        existing_identities
        and existing_identities != {expected_identity}
        and not allow_policy_rebuild
    ):
        raise ValueError(
            "Existing watchlist has a different or legacy policy identity; "
            "explicit rebuild is required"
        )

    scope = warehouse_transaction(conn) if manage_transaction else nullcontext(conn)
    with scope:
        conn.execute("DELETE FROM daily_watchlist WHERE date = ?", [date])

        for rank, candidate in enumerate(candidates, start=1):
            risk_flags = candidate.get("risk_flags_json", [])
            lineage = candidate.get("lineage_json", {})
            conn.execute(
                """
            INSERT INTO daily_watchlist
            (date, rank, symbol, score, candidate_class, setup_type, risk_flags_json, lineage_json,
             scoring_policy_id, scoring_policy_version, scoring_policy_hash, scoring_policy_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    date,
                    rank,
                    candidate["symbol"],
                    candidate["score"],
                    candidate["candidate_class"],
                    candidate["setup_type"],
                    json.dumps(risk_flags)
                    if isinstance(risk_flags, list)
                    else risk_flags,
                    json.dumps(lineage) if isinstance(lineage, dict) else lineage,
                    candidate.get("scoring_policy_id"),
                    candidate.get("scoring_policy_version"),
                    candidate.get("scoring_policy_hash"),
                    candidate.get("scoring_policy_status"),
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
    scoring_policy_id: str = BASELINE_SCORING_POLICY.policy_id,
    scoring_policy_version: str = BASELINE_SCORING_POLICY.version,
    rebuild_policy: bool = False,
    scoring_policy_auto: bool = False,
) -> dict:
    """Full pipeline: compute scores → persist → derive watchlist from persisted data.

    Returns:
        dict with "scored" count (all symbols scored) and "saved" count (watchlist entries).
    """
    policy = resolve_scoring_policy(
        scoring_policy_id,
        scoring_policy_version,
        as_of_date=date,
        conn=conn,
        use_active_default=scoring_policy_auto,
    )
    requested_symbols = sorted(set(universe or ()))
    requested_count = len(requested_symbols) if universe is not None else 0
    try:
        from vnalpha.observability.domain import log_watchlist_start

        log_watchlist_start(date)
    except Exception:  # noqa: BLE001
        pass
    try:
        with warehouse_transaction(conn):
            scored = score_universe(
                conn,
                date,
                universe=universe,
                scoring_policy_id=scoring_policy_id,
                scoring_policy_version=scoring_policy_version,
                rebuild_policy=rebuild_policy,
                project_memory=False,
                scoring_policy_auto=scoring_policy_auto,
            )
            saved = save_watchlist(
                conn,
                date,
                top_n=top_n,
                min_score=min_score,
                scoring_policy_id=policy.policy_id,
                scoring_policy_version=policy.version,
                allow_policy_rebuild=rebuild_policy,
                manage_transaction=False,
                scoring_policy_auto=scoring_policy_auto,
            )
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
    if universe is not None:
        requested_set = set(requested_symbols)
        for scored_result in get_candidate_scores(conn, date):
            if str(scored_result["symbol"]) in requested_set:
                _project_candidate_score_to_memory(
                    conn,
                    str(scored_result["symbol"]),
                    scored_result["date"],
                    scored_result,
                    memory_root=None,
                )
    missing_count = max(0, requested_count - scored) if universe is not None else 0
    return {
        "scored": scored,
        "saved": saved,
        "requested": requested_count,
        "missing": missing_count,
        "scoring_policy_id": policy.policy_id,
        "scoring_policy_version": policy.version,
        "scoring_policy_hash": policy.payload_hash,
        "scoring_policy_status": policy.lifecycle_status.value,
    }
