from datetime import date

import pytest

from vnalpha.ingestion.ohlcv_gap_repository import (
    GapObservationWrite,
    persist_gap_observations,
)
from vnalpha.ingestion.ohlcv_gaps import OHLCVGap, OHLCVGapKind
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


@pytest.mark.parametrize("quality_status", [None, "warn", "skipped", "unknown"])
def test_watermark_ignores_unverified_raw_rows(conn, quality_status) -> None:
    conn.execute(
        """
        INSERT INTO market_ohlcv_raw
            (ingestion_run_id, symbol, time, interval, close, quality_status)
        VALUES ('run-unverified', 'FPT', '2026-09-02', '1D', 101.0, ?)
        """,
        [quality_status],
    )
    request = OHLCVWatermarkRequest(
        symbol="FPT",
        interval="1D",
        requested_start=date(2026, 8, 1),
    )

    watermark = OHLCVWatermarkService().resolve(conn, request)

    assert watermark.last_raw_date is None
    assert watermark.next_request_start == date(2026, 8, 1)


@pytest.mark.parametrize("quality_status", [None, "warn", "skipped", "unknown"])
def test_watermark_ignores_unverified_legacy_canonical_rows(
    conn, quality_status
) -> None:
    conn.execute(
        """
        INSERT INTO canonical_ohlcv
            (symbol, time, interval, close, quality_status)
        VALUES ('FPT', '2026-09-02', '1D', 101.0, ?)
        """,
        [quality_status],
    )
    request = OHLCVWatermarkRequest(
        symbol="FPT",
        interval="1D",
        requested_start=date(2026, 8, 1),
    )

    watermark = OHLCVWatermarkService().resolve(conn, request)

    assert watermark.last_canonical_date is None
    assert watermark.next_request_start == date(2026, 8, 1)


@pytest.mark.parametrize(
    ("price_basis", "expected_date"),
    [
        (None, None),
        ("ADJUSTED", None),
        ("RAW_UNADJUSTED", date(2026, 9, 2)),
    ],
)
def test_fiinquantx_raw_watermark_requires_raw_unadjusted_basis(
    conn, price_basis, expected_date
) -> None:
    conn.execute(
        "INSERT INTO market_ohlcv_raw "
        "(ingestion_run_id, symbol, time, interval, close, provider, "
        "price_basis, quality_status) VALUES "
        "('run-fq', 'FPT', '2026-09-02', '1D', 101.0, 'FIINQUANTX', ?, 'PASS')",
        [price_basis],
    )
    request = OHLCVWatermarkRequest(
        symbol="FPT", interval="1D", requested_start=date(2026, 8, 1)
    )

    watermark = OHLCVWatermarkService().resolve(conn, request)

    assert watermark.last_raw_date == expected_date


@pytest.mark.parametrize(
    ("price_basis", "expected_date"),
    [
        (None, None),
        ("ADJUSTED", None),
        ("RAW_UNADJUSTED", date(2026, 9, 2)),
    ],
)
def test_fiinquantx_canonical_watermark_requires_raw_unadjusted_basis(
    conn, price_basis, expected_date
) -> None:
    conn.execute(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, close, selected_provider, price_basis, "
        "quality_status) VALUES "
        "('FPT', '2026-09-02', '1D', 101.0, 'FIINQUANTX', ?, 'PASS')",
        [price_basis],
    )
    request = OHLCVWatermarkRequest(
        symbol="FPT", interval="1D", requested_start=date(2026, 8, 1)
    )

    watermark = OHLCVWatermarkService().resolve(conn, request)

    assert watermark.last_canonical_date == expected_date


def test_gap_observations_upsert_current_state_with_audit_correlation(conn) -> None:
    # Given
    write = GapObservationWrite(
        symbol="FPT",
        interval="1D",
        calendar_version="vn-session-v1",
        correlation_id="corr-79",
        gaps=(
            OHLCVGap(
                session_date=date(2026, 9, 2),
                kind=OHLCVGapKind.TRUE_GAP,
            ),
        ),
    )

    # When
    persisted = persist_gap_observations(conn, write)

    # Then
    row = conn.execute(
        """
        SELECT symbol, interval, session_date, gap_kind, calendar_version,
               correlation_id, resolved_at
        FROM ohlcv_gap_observation
        """
    ).fetchone()
    assert persisted == 1
    assert row == (
        "FPT",
        "1D",
        date(2026, 9, 2),
        "TRUE_GAP",
        "vn-session-v1",
        "corr-79",
        None,
    )
