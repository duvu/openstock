from datetime import date
from unittest.mock import MagicMock

import pytest

from vnalpha.ingestion.models import (
    BatchIngestionStatus,
    OHLCVBatchResult,
    SymbolIngestionResult,
    SymbolIngestionStatus,
)
from vnalpha.ingestion.ohlcv_maintenance import (
    DailyOHLCVSyncRequest,
    DailyOHLCVSyncService,
    OHLCVGapScanRequest,
    OHLCVGapScanService,
)
from vnalpha.ingestion.trading_calendar import SessionRange
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import upsert_symbol


@pytest.fixture
def conn():
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def test_daily_sync_uses_watermark_overlap_and_rebuilds_each_symbol(conn) -> None:
    # Given
    upsert_symbol(conn, "FPT")
    conn.execute(
        """
        INSERT INTO canonical_ohlcv (symbol, time, interval, close)
        VALUES ('FPT', '2026-09-01', '1D', 100.0)
        """
    )
    batch = OHLCVBatchResult(
        run_id="daily-run",
        status=BatchIngestionStatus.SUCCESS,
        symbol_results=(
            SymbolIngestionResult(
                symbol="FPT",
                status=SymbolIngestionStatus.SUCCESS,
                requested_start="2026-08-31",
                requested_end="2026-09-02",
                provider="KBS",
                rows_inserted=2,
            ),
        ),
        terminal_reason="all_required_symbols_completed",
    )
    fetch_ohlcv = MagicMock(return_value=batch)
    build_canonical = MagicMock(return_value={"upserted": 2, "rejected": 0})
    service = DailyOHLCVSyncService(
        fetch_ohlcv=fetch_ohlcv,
        build_canonical=build_canonical,
    )

    # When
    result = service.sync(
        conn,
        DailyOHLCVSyncRequest(resolved_market_date=date(2026, 9, 2)),
    )

    # Then
    assert result.status is BatchIngestionStatus.SUCCESS
    assert result.watermarks[0].next_request_start == date(2026, 8, 31)
    fetch_ohlcv.assert_called_once_with(
        conn,
        universe=["FPT"],
        start="2026-08-31",
        end="2026-09-02",
        interval="1D",
        source=None,
    )
    build_canonical.assert_called_once_with(conn, symbol="FPT", interval="1D")


def test_gap_scan_persists_true_gap_observation_with_current_correlation(conn) -> None:
    # Given
    conn.execute(
        """
        INSERT INTO canonical_ohlcv (symbol, time, interval, close)
        VALUES ('FPT', '2026-09-01', '1D', 100.0)
        """
    )
    request = OHLCVGapScanRequest(
        symbol="FPT",
        interval="1D",
        session_range=SessionRange(start=date(2026, 9, 1), end=date(2026, 9, 2)),
    )

    # When
    result = OHLCVGapScanService().scan(conn, request)

    # Then
    assert result.report.true_gap_dates == (date(2026, 9, 2),)
    assert (
        conn.execute(
            """
        SELECT gap_kind, correlation_id
        FROM ohlcv_gap_observation
        WHERE symbol = 'FPT' AND session_date = '2026-09-02'
        """
        ).fetchone()[0]
        == "TRUE_GAP"
    )
