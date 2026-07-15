"""Durable current-state evidence for canonical OHLCV session gaps."""

from dataclasses import dataclass
from datetime import date

import duckdb

from vnalpha.ingestion.ohlcv_gaps import OHLCVGap


@dataclass(frozen=True, slots=True)
class GapObservationWrite:
    """One correlation-linked set of observed missing sessions."""

    symbol: str
    interval: str
    calendar_version: str
    correlation_id: str
    gaps: tuple[OHLCVGap, ...]


@dataclass(frozen=True, slots=True)
class GapObservationResolution:
    """Canonical sessions that resolve currently open gap observations."""

    symbol: str
    interval: str
    canonical_sessions: frozenset[date]
    resolution_ref: str


def persist_gap_observations(
    conn: duckdb.DuckDBPyConnection,
    write: GapObservationWrite,
) -> int:
    """Upsert current gap classifications without erasing their first observation."""
    for gap in write.gaps:
        conn.execute(
            """
            INSERT INTO ohlcv_gap_observation
                (symbol, interval, session_date, gap_kind, calendar_version,
                 first_observed_at, last_observed_at, correlation_id, resolved_at,
                 resolution_ref)
            VALUES (?, ?, ?, ?, ?, current_timestamp, current_timestamp, ?, NULL, NULL)
            ON CONFLICT (symbol, interval, session_date) DO UPDATE SET
                gap_kind = excluded.gap_kind,
                calendar_version = excluded.calendar_version,
                last_observed_at = excluded.last_observed_at,
                correlation_id = excluded.correlation_id,
                resolved_at = NULL,
                resolution_ref = NULL
            """,
            [
                write.symbol,
                write.interval,
                gap.session_date,
                gap.kind.value,
                write.calendar_version,
                write.correlation_id,
            ],
        )
    return len(write.gaps)


def resolve_gap_observations(
    conn: duckdb.DuckDBPyConnection,
    resolution: GapObservationResolution,
) -> int:
    """Close only observed sessions now backed by canonical OHLCV bars."""
    for session_date in resolution.canonical_sessions:
        conn.execute(
            """
            UPDATE ohlcv_gap_observation
            SET resolved_at = current_timestamp, resolution_ref = ?
            WHERE symbol = ?
              AND interval = ?
              AND session_date = ?
              AND resolved_at IS NULL
            """,
            [
                resolution.resolution_ref,
                resolution.symbol,
                resolution.interval,
                session_date,
            ],
        )
    return len(resolution.canonical_sessions)
