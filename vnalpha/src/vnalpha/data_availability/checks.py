"""Data availability checks — read-only queries against the warehouse."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as DateType
from datetime import timedelta
from typing import Optional

import duckdb

from vnalpha.data_availability.dates import normalize_explicit_date
from vnalpha.data_availability.models import ArtifactEvidence, DataArtifact


@dataclass(frozen=True, slots=True)
class CandidateScoreEvidence:
    exists: bool
    candidate_class: str | None = None
    as_of_bar_date: str | None = None
    quality_status: str | None = None
    lineage_fields: frozenset[str] = frozenset()
    provider: str | None = None
    ingestion_run_id: str | None = None
    methodology_version: str | None = None
    feature_build_version: str | None = None
    scoring_version: str | None = None
    generated_at: str | None = None


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


def get_latest_canonical_bar_date(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    target_date: str,
) -> Optional[str]:
    """Return the latest canonical OHLCV bar date at or before *target_date*.

    Returns an ISO ``YYYY-MM-DD`` string, or ``None`` when the symbol has no
    canonical bars in range. Used to decide whether an incremental OHLCV sync is
    warranted when history is otherwise sufficient but stale.
    """
    row = conn.execute(
        """
        SELECT MAX(CAST(time AS DATE))::VARCHAR FROM canonical_ohlcv
        WHERE symbol = ?
          AND interval = '1D'
          AND CAST(time AS DATE) <= ?
        """,
        [symbol, target_date],
    ).fetchone()
    if row and row[0]:
        return row[0]
    return None


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
        """
        SELECT 1 FROM feature_snapshot
        WHERE symbol = ? AND date = ? AND as_of_bar_date = ?
          AND feature_data_status = 'EXACT_DATE'
          AND feature_profile IN ('STANDARD_120', 'FULL_252')
          AND neutral_completeness = 'COMPLETE'
          AND relative_strength_completeness = 'COMPLETE'
        LIMIT 1
        """,
        [symbol, target_date, target_date],
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
               cs.scoring_policy_id, cs.scoring_policy_version,
               cs.scoring_policy_hash, cs.scoring_policy_status,
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
    (
        candidate_class,
        lineage_raw,
        policy_id,
        policy_version,
        policy_hash,
        policy_status,
        quality_status,
    ) = row
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
    for key, persisted_value in (
        ("scoring_policy_id", policy_id),
        ("scoring_policy_version", policy_version),
        ("scoring_policy_hash", policy_hash),
        ("scoring_policy_status", policy_status),
    ):
        if persisted_value in (None, "") or lineage.get(key) != persisted_value:
            lineage.pop(key, None)
    lineage_fields = frozenset(
        str(key) for key, value in lineage.items() if value not in (None, "")
    )
    return CandidateScoreEvidence(
        exists=True,
        candidate_class=str(candidate_class),
        as_of_bar_date=str(as_of_bar_date) if as_of_bar_date else None,
        quality_status=str(quality_status) if quality_status else None,
        lineage_fields=lineage_fields,
        provider=_lineage_value(lineage, "selected_provider", "provider"),
        ingestion_run_id=_lineage_value(lineage, "ingestion_run_id"),
        methodology_version=_lineage_value(
            lineage, "feature_build_version", "scoring_version"
        ),
        feature_build_version=_lineage_value(lineage, "feature_build_version"),
        scoring_version=_lineage_value(lineage, "scoring_version"),
        generated_at=_lineage_value(lineage, "score_generated_at", "generated_at"),
    )


def get_symbol_master_evidence(
    conn: duckdb.DuckDBPyConnection, symbol: str
) -> ArtifactEvidence:
    row = conn.execute(
        """
        SELECT last_seen_at::VARCHAR, is_active, exchange, name, sector, industry
        FROM symbol_master WHERE symbol = ? LIMIT 1
        """,
        [symbol],
    ).fetchone()
    return ArtifactEvidence(
        artifact=DataArtifact.SYMBOL_MASTER,
        available=row is not None,
        observed_as_of_date=_date_text(row[0]) if row else None,
        freshness="ready" if row else "missing",
        source_symbol=symbol,
        symbol_metadata=(
            tuple(
                (name, str(value))
                for name, value in zip(
                    ("is_active", "exchange", "name", "sector", "industry"),
                    row[1:],
                    strict=True,
                )
                if value is not None
            )
            if row
            else ()
        ),
    )


def get_ohlcv_evidence(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    target_date: str,
    lookback_start: str,
    artifact: DataArtifact,
) -> ArtifactEvidence:
    summary = conn.execute(
        """
        SELECT COUNT(*), MIN(CAST(time AS DATE))::VARCHAR, MAX(CAST(time AS DATE))::VARCHAR
        FROM canonical_ohlcv
        WHERE symbol = ? AND interval = '1D'
          AND CAST(time AS DATE) >= ? AND CAST(time AS DATE) <= ?
        """,
        [symbol, lookback_start, target_date],
    ).fetchone()
    metadata = conn.execute(
        """
        SELECT selected_provider, quality_status, ingestion_run_id, source_service_run_id
        FROM canonical_ohlcv
        WHERE symbol = ? AND interval = '1D' AND CAST(time AS DATE) <= ?
        ORDER BY time DESC LIMIT 1
        """,
        [symbol, target_date],
    ).fetchone()
    row_count = int(summary[0]) if summary else 0
    provider, quality_status, ingestion_run_id, source_service_run_id = (
        metadata if metadata else (None, None, None, None)
    )
    lineage_fields = frozenset(
        name
        for name, value in {
            "ingestion_run_id": ingestion_run_id,
            "source_service_run_id": source_service_run_id,
        }.items()
        if value
    )
    return ArtifactEvidence(
        artifact=artifact,
        available=row_count > 0,
        row_count=row_count,
        required_row_count=None,
        window_start_date=summary[1] if summary else None,
        observed_as_of_date=summary[2] if summary else None,
        freshness=_freshness(
            row_count > 0, summary[2] if summary else None, target_date
        ),
        quality_status=str(quality_status) if quality_status else "unknown",
        lineage_status="complete" if lineage_fields else "unknown",
        lineage_fields=lineage_fields,
        provider=str(provider) if provider else None,
        ingestion_run_id=str(ingestion_run_id) if ingestion_run_id else None,
        source_symbol=symbol,
    )


def get_feature_snapshot_evidence(
    conn: duckdb.DuckDBPyConnection, symbol: str, target_date: str
) -> ArtifactEvidence:
    row = conn.execute(
        """
        SELECT as_of_bar_date::VARCHAR, benchmark_as_of_bar_date::VARCHAR,
               source_row_count, benchmark_row_count, feature_data_status,
               feature_build_version, feature_generated_at::VARCHAR, lineage_json,
               feature_profile, neutral_completeness,
               relative_strength_completeness
        FROM feature_snapshot WHERE symbol = ? AND date = ? LIMIT 1
        """,
        [symbol, target_date],
    ).fetchone()
    if row is None:
        return ArtifactEvidence(
            artifact=DataArtifact.FEATURE_SNAPSHOT,
            available=False,
            freshness="missing",
        )
    (
        as_of_bar_date,
        benchmark_as_of,
        source_row_count,
        benchmark_count,
        status,
        version,
        generated_at,
        lineage_raw,
        feature_profile,
        neutral_completeness,
        relative_strength_completeness,
    ) = row
    lineage = _decode_lineage(lineage_raw)
    available = (
        _date_text(as_of_bar_date) == target_date
        and str(status) == "EXACT_DATE"
        and str(feature_profile) in {"STANDARD_120", "FULL_252"}
        and str(neutral_completeness) == "COMPLETE"
        and str(relative_strength_completeness) == "COMPLETE"
    )
    return ArtifactEvidence(
        artifact=DataArtifact.FEATURE_SNAPSHOT,
        available=available,
        row_count=int(source_row_count) if source_row_count is not None else None,
        observed_as_of_date=_date_text(as_of_bar_date),
        freshness=_freshness(True, as_of_bar_date, target_date),
        quality_status=(
            str(status) if available and status else "INCOMPLETE_FEATURE_PROFILE"
        ),
        lineage_status="complete" if lineage else "unknown",
        lineage_fields=_lineage_fields(lineage),
        provider=_lineage_value(lineage, "selected_provider", "provider"),
        ingestion_run_id=_lineage_value(lineage, "ingestion_run_id"),
        generated_at=str(generated_at) if generated_at else None,
        methodology_version=str(version) if version else None,
        feature_build_version=str(version) if version else None,
        benchmark_as_of_date=_date_text(benchmark_as_of),
        benchmark_row_count=int(benchmark_count)
        if benchmark_count is not None
        else None,
        source_symbol=symbol,
    )


def get_candidate_score_artifact_evidence(
    conn: duckdb.DuckDBPyConnection, symbol: str, target_date: str
) -> ArtifactEvidence:
    evidence = get_candidate_score_evidence(conn, symbol, target_date)
    return ArtifactEvidence(
        artifact=DataArtifact.CANDIDATE_SCORE,
        available=evidence.exists,
        row_count=1 if evidence.exists else 0,
        observed_as_of_date=evidence.as_of_bar_date,
        freshness=_freshness(evidence.exists, evidence.as_of_bar_date, target_date),
        quality_status=evidence.quality_status or "unknown",
        lineage_status="complete" if evidence.lineage_fields else "unknown",
        lineage_fields=evidence.lineage_fields,
        provider=evidence.provider,
        ingestion_run_id=evidence.ingestion_run_id,
        generated_at=evidence.generated_at,
        methodology_version=evidence.methodology_version,
        feature_build_version=evidence.feature_build_version,
        scoring_version=evidence.scoring_version,
        source_symbol=symbol,
    )


def _decode_lineage(lineage_raw: object) -> dict[str, object]:
    if not lineage_raw:
        return {}
    try:
        decoded = (
            json.loads(lineage_raw) if isinstance(lineage_raw, str) else lineage_raw
        )
    except (json.JSONDecodeError, TypeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _lineage_fields(lineage: dict[str, object]) -> frozenset[str]:
    return frozenset(
        str(key) for key, value in lineage.items() if value not in (None, "")
    )


def _lineage_value(lineage: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = lineage.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _date_text(value: object) -> str | None:
    return str(value)[:10] if value else None


def _freshness(available: bool, observed_date: object, target_date: str) -> str:
    if not available:
        return "missing"
    observed = _parse_date(str(observed_date)) if observed_date else None
    target = _parse_date(target_date)
    if observed is None or target is None:
        return "unknown"
    return "stale" if (target - observed).days > 7 else "ready"


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
