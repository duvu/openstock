"""Warehouse-backed inspection of missing canonical OHLCV sessions."""

from dataclasses import dataclass
from datetime import date

import duckdb

from vnalpha.ingestion.ohlcv_gaps import (
    GapDetectionInput,
    LifecycleState,
    OHLCVGapReport,
    detect_ohlcv_gaps,
)
from vnalpha.ingestion.trading_calendar import SessionRange, VietnamSessionCalendar


@dataclass(frozen=True, slots=True)
class OHLCVGapInspectionRequest:
    """Bounded canonical-gap inspection inputs for one symbol and interval."""

    symbol: str
    interval: str
    session_range: SessionRange
    resolved_market_date: date
    provider_empty_sessions: frozenset[date] = frozenset()


@dataclass(frozen=True, slots=True)
class OHLCVGapInspectionService:
    """Classify canonical-session gaps using calendar and lifecycle evidence."""

    calendar: VietnamSessionCalendar = VietnamSessionCalendar()

    def inspect(
        self,
        conn: duckdb.DuckDBPyConnection,
        request: OHLCVGapInspectionRequest,
    ) -> OHLCVGapReport:
        """Return each missing expected session with its distinct cause."""
        expected_sessions = self.calendar.sessions(request.session_range)
        canonical_sessions = _canonical_sessions(conn, request)
        lifecycle = _lifecycle_state(conn, request.symbol)
        reports = tuple(
            detect_ohlcv_gaps(
                GapDetectionInput(
                    expected_sessions=(session_date,),
                    canonical_sessions=canonical_sessions,
                    lifecycle=lifecycle,
                    resolved_market_date=request.resolved_market_date,
                    provider_empty=session_date in request.provider_empty_sessions,
                )
            )
            for session_date in expected_sessions
        )
        return OHLCVGapReport(
            gaps=tuple(gap for report in reports for gap in report.gaps)
        )


def canonical_sessions_for_request(
    conn: duckdb.DuckDBPyConnection,
    request: OHLCVGapInspectionRequest,
) -> frozenset[date]:
    """Expose canonical sessions for repair resolution without broad querying."""
    return _canonical_sessions(conn, request)


def _canonical_sessions(
    conn: duckdb.DuckDBPyConnection,
    request: OHLCVGapInspectionRequest,
) -> frozenset[date]:
    rows = conn.execute(
        """
        SELECT CAST(time AS DATE)
        FROM canonical_ohlcv
        WHERE symbol = ?
          AND interval = ?
          AND CAST(time AS DATE) BETWEEN ? AND ?
        """,
        [
            request.symbol,
            request.interval,
            request.session_range.start,
            request.session_range.end,
        ],
    ).fetchall()
    return frozenset(row[0] for row in rows)


def _lifecycle_state(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
) -> LifecycleState:
    row = conn.execute(
        "SELECT lifecycle_status FROM symbol_master WHERE symbol = ?",
        [symbol],
    ).fetchone()
    if row is None or not isinstance(row[0], str):
        return LifecycleState.ACTIVE
    match row[0].strip().upper():
        case "ACTIVE":
            return LifecycleState.ACTIVE
        case "SUSPENDED":
            return LifecycleState.SUSPENDED
        case "INACTIVE" | "DELISTED":
            return LifecycleState.INACTIVE
        case _:
            return LifecycleState.INACTIVE
