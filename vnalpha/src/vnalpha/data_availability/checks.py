"""Data availability checks — read-only queries against the warehouse."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as DateType
from datetime import timedelta
from typing import Optional

import duckdb

from vnalpha.data_availability.dates import normalize_explicit_date


@dataclass(frozen=True, slots=True)
class CandidateScoreEvidence:
    exists: bool
    candidate_class: str | None = None
    as_of_bar_date: str | None = None
    quality_status: str | None = None
    lineage_fields: frozenset[str] = frozenset()


def get_symbol_master_status(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
) -> bool:
    """Return True if the symbol exists in symbol_master (active or inactive)."""
    row = conn.execute(
        "SELECT 1 FROM symbol_master WHERE symbol = ? LIMIT 1",
        [symbol],
    ).fetchone()
    return row is not None


def get_canonical_ohlcv_status(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    target_date: str,
    lookback_start: str,
) -> int:
    """Return number of canonical OHLCV bars for the symbol in [lookback_start, target_date]."""
    row = conn.execute(
        """
        SELECT COUNT(*) FROM canonical_ohlcv
        WHERE symbol = ?
          AND interval = '1D'
          AND CAST(time AS DATE) >= ?
          AND CAST(time AS DATE) <= ?
        """,
        [symbol, lookback_start, target_date],
    ).fetchone()
    return row[0] if row else 0


def get_benchmark_status(
    conn: duckdb.DuckDBPyConnection,
    benchmark: str,
    target_date: str,
    lookback_start: str,
) -> int:
    """Return number of canonical OHLCV bars for benchmark in [lookback_start, target_date]."""
    return get_canonical_ohlcv_status(conn, benchmark, target_date, lookback_start)


def get_feature_snapshot_status(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    target_date: str,
) -> bool:
    """Return True if a feature_snapshot row exists for (symbol, date)."""
    row = conn.execute(
        "SELECT 1 FROM feature_snapshot WHERE symbol = ? AND date = ? LIMIT 1",
        [symbol, target_date],
    ).fetchone()
    return row is not None


def get_candidate_score_status(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    target_date: str,
    stale_after_calendar_days: int = 7,
) -> Optional[str]:
    """Return candidate_class if a fresh candidate_score exists, else None.

    A score is considered stale if the feature_data lineage bar_date (as_of_bar_date
    in lineage_json) is more than *stale_after_calendar_days* before target_date.
    In practice, for intra-session freshness we only check existence — the stale
    threshold guards against day-old pipeline runs.
    """
    evidence = get_candidate_score_evidence(conn, symbol, target_date)
    if not evidence.exists:
        return None
    if evidence.as_of_bar_date and stale_after_calendar_days > 0:
        bar_dt = _parse_date(evidence.as_of_bar_date)
        target_dt = _parse_date(target_date)
        if (
            bar_dt
            and target_dt
            and (target_dt - bar_dt).days > stale_after_calendar_days
        ):
            return None
    return evidence.candidate_class


def get_candidate_score_evidence(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    target_date: str,
) -> CandidateScoreEvidence:
    """Return parsed score, quality, and lineage evidence for cache policy."""

    row = conn.execute(
        """
        SELECT cs.candidate_class, cs.lineage_json,
               (
                   SELECT co.quality_status
                   FROM canonical_ohlcv co
                   WHERE co.symbol = cs.symbol
                     AND co.interval = '1D'
                     AND CAST(co.time AS DATE) <= cs.date
                   ORDER BY co.time DESC
                   LIMIT 1
               ) AS quality_status
        FROM candidate_score cs
        WHERE cs.symbol = ? AND cs.date = ?
        LIMIT 1
        """,
        [symbol, target_date],
    ).fetchone()
    if row is None:
        return CandidateScoreEvidence(exists=False)
    candidate_class, lineage_raw, quality_status = row
    lineage: dict = {}
    if lineage_raw:
        try:
            decoded = (
                json.loads(lineage_raw) if isinstance(lineage_raw, str) else lineage_raw
            )
            if isinstance(decoded, dict):
                lineage = decoded
        except (json.JSONDecodeError, TypeError):
            lineage = {}
    as_of_bar_date = lineage.get("as_of_bar_date") or lineage.get("feature_date")
    lineage_fields = frozenset(
        str(key) for key, value in lineage.items() if value not in (None, "")
    )
    return CandidateScoreEvidence(
        exists=True,
        candidate_class=str(candidate_class),
        as_of_bar_date=str(as_of_bar_date) if as_of_bar_date else None,
        quality_status=str(quality_status) if quality_status else None,
        lineage_fields=lineage_fields,
    )


def _parse_date(s: str) -> Optional[DateType]:
    """Parse YYYY-MM-DD string to date, returning None on failure."""
    try:
        return DateType.fromisoformat(str(s)[:10])
    except (ValueError, TypeError):
        return None


def compute_lookback_start(target_date: str, lookback_days: int) -> str:
    """Compute the lookback start date as YYYY-MM-DD string."""
    target_dt = DateType.fromisoformat(normalize_explicit_date(target_date))
    lookback_dt = target_dt - timedelta(days=lookback_days)
    return lookback_dt.isoformat()
