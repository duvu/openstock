from datetime import date

import httpx
import pytest
import respx

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.ingestion.ohlcv_repair import OHLCVRepairRequest, OHLCVRepairService
from vnalpha.ingestion.trading_calendar import SessionRange
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations

MOCK_BASE = "http://127.0.0.1:6901"


@pytest.fixture
def conn():
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


@respx.mock(base_url=MOCK_BASE)
def test_repair_fetches_only_true_gap_rebuilds_and_is_idempotent(
    respx_mock, conn
) -> None:
    # Given
    conn.execute(
        """
        INSERT INTO canonical_ohlcv (symbol, time, interval, close)
        VALUES
            ('FPT', '2026-09-01', '1D', 100.0),
            ('FPT', '2026-09-03', '1D', 102.0)
        """
    )
    response_data = {
        "data": [
            {
                "symbol": "FPT",
                "time": "2026-09-02 00:00:00",
                "interval": "1D",
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "volume": 1_000_000.0,
            }
        ],
        "meta": {
            "dataset": "equity.ohlcv",
            "provider": "kbs",
            "quality_status": "pass",
            "fetched_at": "2026-09-02T09:00:00",
        },
        "diagnostics": {},
    }
    route = respx_mock.get("/v1/equity/ohlcv").mock(
        return_value=httpx.Response(200, json=response_data)
    )
    request = OHLCVRepairRequest(
        symbol="FPT",
        interval="1D",
        session_range=SessionRange(start=date(2026, 9, 1), end=date(2026, 9, 3)),
    )
    client = VnstockClient(base_url=MOCK_BASE)
    service = OHLCVRepairService(client=client)

    # When
    repaired = service.repair(conn, request)
    repeated = service.repair(conn, request)

    # Then
    assert repaired.fetched_dates == (date(2026, 9, 2),)
    assert repaired.after.true_gap_dates == ()
    assert repeated.fetched_dates == ()
    assert route.call_count == 1
    assert route.calls[0].request.url.params["start"] == "2026-09-02"
    assert route.calls[0].request.url.params["end"] == "2026-09-02"
    assert conn.execute(
        """
        SELECT gap_kind, resolved_at IS NOT NULL
        FROM ohlcv_gap_observation
        WHERE symbol = 'FPT' AND session_date = '2026-09-02'
        """
    ).fetchone() == ("TRUE_GAP", True)
