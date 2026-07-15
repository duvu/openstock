"""Bounded, idempotent repair of true canonical OHLCV gaps."""

from dataclasses import dataclass
from datetime import date

import duckdb

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.ingestion.build_canonical import build_canonical_ohlcv
from vnalpha.ingestion.ohlcv_gap_inspection import (
    OHLCVGapInspectionRequest,
    OHLCVGapInspectionService,
    canonical_sessions_for_request,
)
from vnalpha.ingestion.ohlcv_gap_repository import (
    GapObservationResolution,
    GapObservationWrite,
    persist_gap_observations,
    resolve_gap_observations,
)
from vnalpha.ingestion.ohlcv_gaps import OHLCVGapReport
from vnalpha.ingestion.sync_ohlcv import sync_ohlcv
from vnalpha.ingestion.trading_calendar import SessionRange, VietnamSessionCalendar
from vnalpha.observability.context import get_correlation_id, set_correlation_id


@dataclass(frozen=True, slots=True)
class OHLCVRepairRequest:
    """A symbol-local date range eligible for exact missing-session repair."""

    symbol: str
    interval: str
    session_range: SessionRange
    source: str | None = None


@dataclass(frozen=True, slots=True)
class OHLCVRepairResult:
    """Repair evidence, including the before/after unresolved classifications."""

    before: OHLCVGapReport
    after: OHLCVGapReport
    fetched_dates: tuple[date, ...]
    provider_empty_dates: tuple[date, ...]


@dataclass(frozen=True, slots=True)
class OHLCVRepairService:
    """Fetch each true gap exactly once, then rebuild canonical OHLCV."""

    calendar: VietnamSessionCalendar = VietnamSessionCalendar()
    client: VnstockClient | None = None

    def repair(
        self,
        conn: duckdb.DuckDBPyConnection,
        request: OHLCVRepairRequest,
    ) -> OHLCVRepairResult:
        """Repair only published active gaps and retain all resulting evidence."""
        if get_correlation_id() in {"", "unset"}:
            set_correlation_id()
        inspection = _inspection_request(request)
        inspector = OHLCVGapInspectionService(calendar=self.calendar)
        before = inspector.inspect(conn, inspection)
        _persist_report(conn, request, self.calendar, before)
        provider_empty_dates = _fetch_true_gaps(
            conn,
            request,
            before.true_gap_dates,
            self.client,
        )
        if before.true_gap_dates:
            build_canonical_ohlcv(
                conn, symbol=request.symbol, interval=request.interval
            )
        after = inspector.inspect(
            conn,
            _inspection_request(request, provider_empty_dates),
        )
        _persist_report(conn, request, self.calendar, after)
        _resolve_present_observations(conn, request, inspection)
        return OHLCVRepairResult(
            before=before,
            after=after,
            fetched_dates=before.true_gap_dates,
            provider_empty_dates=provider_empty_dates,
        )


def _inspection_request(
    request: OHLCVRepairRequest,
    provider_empty_sessions: tuple[date, ...] = (),
) -> OHLCVGapInspectionRequest:
    return OHLCVGapInspectionRequest(
        symbol=request.symbol,
        interval=request.interval,
        session_range=request.session_range,
        resolved_market_date=request.session_range.end,
        provider_empty_sessions=frozenset(provider_empty_sessions),
    )


def _persist_report(
    conn: duckdb.DuckDBPyConnection,
    request: OHLCVRepairRequest,
    calendar: VietnamSessionCalendar,
    report: OHLCVGapReport,
) -> None:
    persist_gap_observations(
        conn,
        GapObservationWrite(
            symbol=request.symbol,
            interval=request.interval,
            calendar_version=calendar.version,
            correlation_id=get_correlation_id(),
            gaps=report.gaps,
        ),
    )


def _fetch_true_gaps(
    conn: duckdb.DuckDBPyConnection,
    request: OHLCVRepairRequest,
    true_gap_dates: tuple[date, ...],
    client: VnstockClient | None,
) -> tuple[date, ...]:
    provider_empty_dates: list[date] = []
    for session_date in true_gap_dates:
        batch = sync_ohlcv(
            conn,
            universe=[request.symbol],
            start=session_date.isoformat(),
            end=session_date.isoformat(),
            interval=request.interval,
            source=request.source,
            client=client,
        )
        if batch.symbol_results[0].status.value == "EMPTY":
            provider_empty_dates.append(session_date)
    return tuple(provider_empty_dates)


def _resolve_present_observations(
    conn: duckdb.DuckDBPyConnection,
    request: OHLCVRepairRequest,
    inspection: OHLCVGapInspectionRequest,
) -> None:
    resolve_gap_observations(
        conn,
        GapObservationResolution(
            symbol=request.symbol,
            interval=request.interval,
            canonical_sessions=canonical_sessions_for_request(conn, inspection),
            resolution_ref=f"repair:{get_correlation_id()}",
        ),
    )
