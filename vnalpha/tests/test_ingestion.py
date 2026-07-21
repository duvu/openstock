"""Tests for ingestion jobs using mocks."""

import httpx
import pytest
import respx

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
