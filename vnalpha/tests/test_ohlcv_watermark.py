from datetime import date

import pytest

from vnalpha.ingestion.ohlcv_watermark import (
    OHLCVWatermarkRequest,
    OHLCVWatermarkService,
)
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn():
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def test_watermark_uses_latest_complete_raw_and_canonical_with_session_overlap(
    conn,
) -> None:
    # Given
    conn.execute(
        """
        INSERT INTO canonical_ohlcv
            (symbol, time, interval, close, quality_status)
        VALUES ('FPT', '2026-07-15', '1D', 100.0, 'pass')
        """
    )
    conn.execute(
        """
        INSERT INTO market_ohlcv_raw
            (ingestion_run_id, symbol, time, interval, close, quality_status)
        VALUES ('run-1', 'FPT', '2026-07-16', '1D', 101.0, 'pass')
        """
    )
    request = OHLCVWatermarkRequest(
        symbol="FPT",
        interval="1D",
        requested_start=date(2026, 7, 1),
        overlap_sessions=2,
    )

    # When
    watermark = OHLCVWatermarkService().resolve(conn, request)

    # Then
    assert watermark.last_canonical_date == date(2026, 7, 15)
    assert watermark.last_raw_date == date(2026, 7, 16)
    assert watermark.next_request_start == date(2026, 7, 15)
