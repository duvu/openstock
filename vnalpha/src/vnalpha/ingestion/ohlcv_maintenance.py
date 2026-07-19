"""Incremental daily OHLCV synchronization from persisted watermarks."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import duckdb

from vnalpha.data_availability.checks import compute_lookback_start
from vnalpha.data_availability.policy import DEFAULT_POLICY
from vnalpha.ingestion.build_canonical import build_canonical_ohlcv
from vnalpha.ingestion.models import BatchIngestionStatus, OHLCVBatchResult
from vnalpha.ingestion.ohlcv_gap_inspection import (
    OHLCVGapInspectionRequest,
    OHLCVGapInspectionService,
)
from vnalpha.ingestion.ohlcv_gap_repository import (
    GapObservationWrite,
    persist_gap_observations,
)
from vnalpha.ingestion.ohlcv_gaps import OHLCVGapReport
from vnalpha.ingestion.ohlcv_watermark import (
    OHLCVWatermark,
    OHLCVWatermarkRequest,
    OHLCVWatermarkService,
)
from vnalpha.ingestion.sync_ohlcv import sync_ohlcv
from vnalpha.ingestion.trading_calendar import SessionRange, VietnamSessionCalendar
from vnalpha.observability.context import get_correlation_id, set_correlation_id
from vnalpha.warehouse.repositories import get_symbols_active


class OHLCVBatchFetcher(Protocol):
    """The bounded provider-sync seam used by daily maintenance."""

    def __call__(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        universe: list[str],
        start: str,
        end: str,
        interval: str,
        source: str | None,
    ) -> OHLCVBatchResult: ...


class CanonicalBuilder(Protocol):
    """The canonical rebuild seam used after each completed fetch."""

    def __call__(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        symbol: str,
        interval: str,
    ) -> Mapping[str, int]: ...


@dataclass(frozen=True, slots=True)
class DailyOHLCVSyncRequest:
    """One daily incremental run over the active research equity universe."""

    resolved_market_date: date
    interval: str = "1D"
    source: str | None = None
    symbols: tuple[str, ...] | None = None
    overlap_sessions: int = 2


@dataclass(frozen=True, slots=True)
class DailyOHLCVSyncResult:
    """Per-symbol watermarks and typed batch outcomes for daily maintenance."""

    watermarks: tuple[OHLCVWatermark, ...]
    batches: tuple[OHLCVBatchResult, ...]
    status: BatchIngestionStatus

    @property
    def rows_inserted(self) -> int:
        """Return rows persisted by all bounded provider requests."""
        return sum(batch.rows_inserted for batch in self.batches)


@dataclass(frozen=True, slots=True)
class DailyOHLCVSyncService:
    """Run one correlation-preserving incremental daily OHLCV maintenance pass."""

    watermark_service: OHLCVWatermarkService = OHLCVWatermarkService()
    fetch_ohlcv: OHLCVBatchFetcher = sync_ohlcv
    build_canonical: CanonicalBuilder = build_canonical_ohlcv

    def sync(
        self,
        conn: duckdb.DuckDBPyConnection,
        request: DailyOHLCVSyncRequest,
    ) -> DailyOHLCVSyncResult:
        """Fetch every active symbol from its overlap watermark through market date."""
        watermarks: list[OHLCVWatermark] = []
        batches: list[OHLCVBatchResult] = []
        symbols = request.symbols or tuple(get_symbols_active(conn))
        for symbol in symbols:
            bootstrap_start = date.fromisoformat(
                compute_lookback_start(
                    request.resolved_market_date.isoformat(),
                    DEFAULT_POLICY.lookback_days,
                )
            )
            watermark = self.watermark_service.resolve(
                conn,
                OHLCVWatermarkRequest(
                    symbol=symbol,
                    interval=request.interval,
                    requested_start=bootstrap_start,
                    overlap_sessions=request.overlap_sessions,
                    overlap_floor=date.min,
                ),
            )
            watermarks.append(watermark)
            batch = self.fetch_ohlcv(
                conn,
                universe=[symbol],
                start=watermark.next_request_start.isoformat(),
                end=request.resolved_market_date.isoformat(),
                interval=request.interval,
                source=request.source,
            )
            batches.append(batch)
            if batch.status is not BatchIngestionStatus.FAILED:
                self.build_canonical(conn, symbol=symbol, interval=request.interval)
        batch_results = tuple(batches)
        return DailyOHLCVSyncResult(
            watermarks=tuple(watermarks),
            batches=batch_results,
            status=_daily_status(batch_results),
        )


def _daily_status(batches: tuple[OHLCVBatchResult, ...]) -> BatchIngestionStatus:
    if not batches:
        return BatchIngestionStatus.FAILED
    if all(batch.status is BatchIngestionStatus.SUCCESS for batch in batches):
        return BatchIngestionStatus.SUCCESS
    if any(batch.status is not BatchIngestionStatus.FAILED for batch in batches):
        return BatchIngestionStatus.PARTIAL
    return BatchIngestionStatus.FAILED


@dataclass(frozen=True, slots=True)
class OHLCVGapScanRequest:
    """One explicitly bounded canonical OHLCV gap scan."""

    symbol: str
    interval: str
    session_range: SessionRange


@dataclass(frozen=True, slots=True)
class OHLCVGapScanResult:
    """Reported missing-session classifications and their persisted count."""

    report: OHLCVGapReport
    persisted_count: int


@dataclass(frozen=True, slots=True)
class OHLCVGapScanService:
    """Inspect and persist typed OHLCV gap evidence without provider access."""

    calendar: VietnamSessionCalendar = VietnamSessionCalendar()

    def scan(
        self,
        conn: duckdb.DuckDBPyConnection,
        request: OHLCVGapScanRequest,
    ) -> OHLCVGapScanResult:
        """Persist every missing expected session under the current correlation."""
        if get_correlation_id() in {"", "unset"}:
            set_correlation_id()
        report = OHLCVGapInspectionService(calendar=self.calendar).inspect(
            conn,
            OHLCVGapInspectionRequest(
                symbol=request.symbol,
                interval=request.interval,
                session_range=request.session_range,
                resolved_market_date=request.session_range.end,
            ),
        )
        persisted_count = persist_gap_observations(
            conn,
            GapObservationWrite(
                symbol=request.symbol,
                interval=request.interval,
                calendar_version=self.calendar.version,
                correlation_id=get_correlation_id(),
                gaps=report.gaps,
            ),
        )
        return OHLCVGapScanResult(
            report=report,
            persisted_count=persisted_count,
        )
