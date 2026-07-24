from __future__ import annotations

from threading import Event, Lock
from unittest.mock import MagicMock

import pytest

from vnalpha.clients.vnstock.errors import VnstockHTTPError
from vnalpha.clients.vnstock.schemas import OHLCVResponse
from vnalpha.ingestion.sync_ohlcv import sync_ohlcv
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn():
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _response(symbol: str, *, rows: int) -> OHLCVResponse:
    data = [
        {
            "symbol": symbol,
            "time": f"2026-07-{day + 1:02d} 00:00:00",
            "interval": "1D",
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
            "volume": 1000.0,
        }
        for day in range(rows)
    ]
    return OHLCVResponse.model_validate(
        {
            "data": data,
            "meta": {
                "request_id": f"req-{symbol.lower()}",
                "dataset": "equity.ohlcv",
                "provider": "KBS",
                "quality_status": "PASS",
            },
            "diagnostics": {"routing": {"selected": "KBS"}},
        }
    )


def test_mixed_batch_cannot_persist_all_success(conn) -> None:
    client = MagicMock()
    concurrent_fetches = 0
    max_concurrent_fetches = 0
    two_downloads_started = Event()
    fetch_lock = Lock()

    def fetch(*, symbol: str, **_kwargs):
        nonlocal concurrent_fetches, max_concurrent_fetches
        with fetch_lock:
            concurrent_fetches += 1
            max_concurrent_fetches = max(max_concurrent_fetches, concurrent_fetches)
            if concurrent_fetches >= 2:
                two_downloads_started.set()
        assert two_downloads_started.wait(timeout=1)
        with fetch_lock:
            concurrent_fetches -= 1
        if symbol == "FPT":
            return _response(symbol, rows=1)
        if symbol == "VNM":
            return _response(symbol, rows=0)
        raise VnstockHTTPError(503, "/v1/equity/ohlcv", "provider unavailable")

    client.get_equity_ohlcv.side_effect = fetch

    result = sync_ohlcv(conn, universe=["FPT", "VNM", "MSN"], client=client)

    assert result["status"] == "PARTIAL"
    assert {item["symbol"]: item["status"] for item in result["symbol_results"]} == {
        "FPT": "SUCCESS",
        "VNM": "EMPTY",
        "MSN": "FAILED",
    }
    persisted = conn.execute(
        "SELECT status FROM ingestion_run WHERE ingestion_run_id = ?",
        [result["run_id"]],
    ).fetchone()
    assert persisted == ("PARTIAL",)
    assert max_concurrent_fetches == 2
