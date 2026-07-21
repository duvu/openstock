"""Tests for the vnstock-service client using respx mock."""

import httpx
import respx

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.clients.vnstock.schemas import (
    SymbolsResponse,
)

MOCK_BASE = "http://127.0.0.1:6900"

SYMBOLS_RESPONSE = {
    "data": [
        {"symbol": "FPT", "exchange": "HOSE", "name": "FPT Corp"},
        {"symbol": "VNM", "exchange": "HOSE", "name": "Vinamilk"},
    ],
    "meta": {
        "dataset": "reference.symbols",
        "provider": "kbs",
        "quality_status": "pass",
        "fetched_at": "2024-01-02T09:00:00",
    },
    "diagnostics": {},
}

OHLCV_RESPONSE = {
    "data": [
        {
            "symbol": "FPT",
            "time": "2024-01-02",
            "open": 90.0,
            "high": 92.0,
            "low": 89.0,
            "close": 91.5,
            "volume": 1_000_000,
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


@respx.mock(base_url=MOCK_BASE)
def test_get_symbols(respx_mock):
    respx_mock.get("/v1/reference/symbols").mock(
        return_value=httpx.Response(200, json=SYMBOLS_RESPONSE)
    )
    client = VnstockClient(base_url=MOCK_BASE)
    result = client.get_symbols()
    assert isinstance(result, SymbolsResponse)
    assert len(result.data) == 2
    assert result.meta.provider == "kbs"
    request = respx_mock.calls.last.request
    assert request.url.params["validate"] == "true"
    assert request.url.params["quality_mode"] == "strict"
