"""Incremental request watermarks for canonical and raw OHLCV data."""

from dataclasses import dataclass
from datetime import date

import duckdb

from vnalpha.ingestion.trading_calendar import VietnamSessionCalendar


@dataclass(frozen=True, slots=True)
class OHLCVWatermarkRequest:
    """One incremental OHLCV request with an inclusive session overlap."""

    symbol: str
    interval: str
    requested_start: date
    overlap_sessions: int = 2
    overlap_floor: date | None = None


@dataclass(frozen=True, slots=True)
class OHLCVWatermark:
    """Latest complete canonical/raw bars and the next safe provider start."""

    symbol: str
    interval: str
    last_canonical_date: date | None
    last_raw_date: date | None
    next_request_start: date


@dataclass(frozen=True, slots=True)
class OHLCVWatermarkService:
    """Resolve deterministic per-symbol incremental OHLCV watermarks."""

    calendar: VietnamSessionCalendar = VietnamSessionCalendar()

    def resolve(
        self,
        conn: duckdb.DuckDBPyConnection,
        request: OHLCVWatermarkRequest,
    ) -> OHLCVWatermark:
        """Read canonical/raw completion markers and preserve safe overlap."""
        canonical_date = _latest_canonical_date(conn, request)
        raw_date = _latest_complete_raw_date(conn, request)
        latest_date = _latest_available_date(canonical_date, raw_date)
        next_request_start = _next_request_start(
            request,
            latest_date,
            self.calendar,
        )
        return OHLCVWatermark(
            symbol=request.symbol,
            interval=request.interval,
            last_canonical_date=canonical_date,
            last_raw_date=raw_date,
            next_request_start=next_request_start,
        )


def _latest_canonical_date(
    conn: duckdb.DuckDBPyConnection,
    request: OHLCVWatermarkRequest,
) -> date | None:
    row = conn.execute(
        """
        SELECT MAX(CAST(time AS DATE))
        FROM canonical_ohlcv
        WHERE symbol = ? AND interval = ?
        """,
        [request.symbol, request.interval],
    ).fetchone()
    return row[0] if row is not None else None


def _latest_complete_raw_date(
    conn: duckdb.DuckDBPyConnection,
    request: OHLCVWatermarkRequest,
) -> date | None:
    row = conn.execute(
        """
        SELECT MAX(CAST(time AS DATE))
        FROM market_ohlcv_raw
        WHERE symbol = ?
          AND interval = ?
          AND LOWER(TRIM(COALESCE(quality_status, ''))) NOT IN ('error', 'fail', 'failed', 'invalid')
        """,
        [request.symbol, request.interval],
    ).fetchone()
    return row[0] if row is not None else None


def _latest_available_date(
    canonical_date: date | None,
    raw_date: date | None,
) -> date | None:
    dates = tuple(value for value in (canonical_date, raw_date) if value is not None)
    return max(dates) if dates else None


def _next_request_start(
    request: OHLCVWatermarkRequest,
    latest_date: date | None,
    calendar: VietnamSessionCalendar,
) -> date:
    if latest_date is None:
        return request.requested_start
    overlap_start = calendar.rewind_sessions(latest_date, request.overlap_sessions)
    floor = request.overlap_floor or request.requested_start
    return max(floor, overlap_start)
