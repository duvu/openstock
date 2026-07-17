"""Tests for ingestion jobs using mocks."""

from unittest.mock import MagicMock

import httpx
import pytest
import respx

from vnalpha.ingestion.build_canonical import build_canonical_ohlcv
from vnalpha.ingestion.sync_ohlcv import sync_ohlcv
from vnalpha.ingestion.sync_symbols import sync_symbols
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import get_symbols_active

MOCK_BASE = "http://127.0.0.1:6900"

SYMBOLS_DATA = {
    "data": [
        {
            "symbol": "FPT",
            "exchange": "HOSE",
            "name": "FPT Corp",
            "sector": "Technology",
        },
        {"symbol": "VNM", "exchange": "HOSE", "name": "Vinamilk", "sector": "Consumer"},
    ],
    "meta": {
        "dataset": "reference.symbols",
        "provider": "kbs",
        "quality_status": "pass",
        "fetched_at": "2024-01-02T09:00:00",
    },
    "diagnostics": {},
}

OHLCV_DATA_FPT = {
    "data": [
        {
            "symbol": "FPT",
            "time": "2024-01-02 00:00:00",
            "interval": "1D",
            "open": 89.0,
            "high": 92.0,
            "low": 88.0,
            "close": 91.5,
            "volume": 1000000.0,
        },
        {
            "symbol": "FPT",
            "time": "2024-01-03 00:00:00",
            "interval": "1D",
            "open": 91.5,
            "high": 93.0,
            "low": 90.0,
            "close": 92.0,
            "volume": 800000.0,
        },
    ],
    "meta": {
        "dataset": "equity.ohlcv",
        "provider": "kbs",
        "quality_status": "pass",
        "fetched_at": "2024-01-03T09:00:00",
    },
    "diagnostics": {},
}

OHLCV_DATA_VNM = {
    "data": [
        {
            "symbol": "VNM",
            "time": "2024-01-02 00:00:00",
            "interval": "1D",
            "open": 70.0,
            "high": 72.0,
            "low": 69.0,
            "close": 71.0,
            "volume": 500000.0,
        },
    ],
    "meta": {
        "dataset": "equity.ohlcv",
        "provider": "kbs",
        "quality_status": "pass",
        "fetched_at": "2024-01-02T09:00:00",
    },
    "diagnostics": {},
}


@pytest.fixture
def conn():
    c = in_memory_connection()
    run_migrations(conn=c)
    yield c
    c.close()


@respx.mock(base_url=MOCK_BASE)
def test_sync_symbols_inserts_records(respx_mock, conn):
    respx_mock.get("/v1/reference/symbols").mock(
        return_value=httpx.Response(200, json=SYMBOLS_DATA)
    )
    from vnalpha.clients.vnstock.client import VnstockClient

    client = VnstockClient(base_url=MOCK_BASE)
    result = sync_symbols(conn, client=client)
    assert result["synced"] == 2
    assert result["errors"] == 0
    request = respx_mock.calls.last.request
    assert request.url.params["validate"] == "true"
    assert request.url.params["quality_mode"] == "strict"
    symbols = get_symbols_active(conn)
    assert "FPT" in symbols
    assert "VNM" in symbols


@respx.mock(base_url=MOCK_BASE)
def test_sync_ohlcv_inserts_records(respx_mock, conn):
    from vnalpha.clients.vnstock.client import VnstockClient

    def ohlcv_side_effect(request, route):
        symbol = request.url.params.get("symbol", "")
        if symbol == "FPT":
            return httpx.Response(200, json=OHLCV_DATA_FPT)
        elif symbol == "VNM":
            return httpx.Response(200, json=OHLCV_DATA_VNM)
        return httpx.Response(404, json={"error": "not found"})

    respx_mock.get("/v1/equity/ohlcv").mock(side_effect=ohlcv_side_effect)
    client = VnstockClient(base_url=MOCK_BASE)
    result = sync_ohlcv(conn, universe=["FPT", "VNM"], client=client)
    assert result["total"] == 2
    assert result["inserted"] == 3  # 2 FPT + 1 VNM
    assert result["skipped"] == 0


@respx.mock(base_url=MOCK_BASE)
def test_build_canonical_promotes_raw(respx_mock, conn):
    from vnalpha.clients.vnstock.client import VnstockClient

    def ohlcv_side_effect(request, route):
        return httpx.Response(200, json=OHLCV_DATA_FPT)

    respx_mock.get("/v1/equity/ohlcv").mock(side_effect=ohlcv_side_effect)
    client = VnstockClient(base_url=MOCK_BASE)
    sync_ohlcv(conn, universe=["FPT"], client=client)
    result = build_canonical_ohlcv(conn, symbol="FPT")
    assert result["upserted"] >= 2
    rows = conn.execute(
        "SELECT symbol, close FROM canonical_ohlcv WHERE symbol = 'FPT' ORDER BY time"
    ).fetchall()
    assert len(rows) == 2


@respx.mock(base_url=MOCK_BASE)
def test_sync_symbols_records_ingestion_run(respx_mock, conn):
    respx_mock.get("/v1/reference/symbols").mock(
        return_value=httpx.Response(200, json=SYMBOLS_DATA)
    )
    from vnalpha.clients.vnstock.client import VnstockClient

    client = VnstockClient(base_url=MOCK_BASE)
    result = sync_symbols(conn, client=client)
    run_id = result["run_id"]
    rows = conn.execute(
        "SELECT status FROM ingestion_run WHERE ingestion_run_id = ?", [run_id]
    ).fetchall()
    assert rows[0][0] == "SUCCESS"


def test_sync_symbols_handles_connection_error(conn):
    from vnalpha.clients.vnstock.errors import VnstockConnectionError

    mock_client = MagicMock()
    mock_client.get_symbols.side_effect = VnstockConnectionError("No service")
    with pytest.raises(VnstockConnectionError):
        sync_symbols(conn, client=mock_client)
    # Run should be marked FAILED
    rows = conn.execute(
        "SELECT status FROM ingestion_run ORDER BY started_at DESC LIMIT 1"
    ).fetchall()
    assert rows[0][0] == "FAILED"
