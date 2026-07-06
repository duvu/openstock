"""Tests for the vnstock-service client using respx mock."""

import httpx
import pytest
import respx

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.clients.vnstock.errors import VnstockHTTPError
from vnalpha.clients.vnstock.schemas import (
    OHLCVResponse,
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


@respx.mock(base_url=MOCK_BASE)
def test_get_equity_ohlcv(respx_mock):
    respx_mock.get("/v1/equity/ohlcv").mock(
        return_value=httpx.Response(200, json=OHLCV_RESPONSE)
    )
    client = VnstockClient(base_url=MOCK_BASE)
    result = client.get_equity_ohlcv("FPT", start="2024-01-01")
    assert isinstance(result, OHLCVResponse)
    assert result.data[0]["symbol"] == "FPT"


@respx.mock(base_url=MOCK_BASE)
def test_http_error_raises(respx_mock):
    respx_mock.get("/v1/equity/ohlcv").mock(
        return_value=httpx.Response(503, text="Service unavailable")
    )
    client = VnstockClient(base_url=MOCK_BASE)
    with pytest.raises(VnstockHTTPError) as exc_info:
        client.get_equity_ohlcv("FPT")
    assert exc_info.value.status_code == 503


@respx.mock(base_url=MOCK_BASE)
def test_response_preserves_meta(respx_mock):
    respx_mock.get("/v1/reference/symbols").mock(
        return_value=httpx.Response(200, json=SYMBOLS_RESPONSE)
    )
    client = VnstockClient(base_url=MOCK_BASE)
    result = client.get_symbols()
    assert result.meta.dataset == "reference.symbols"
    assert result.meta.quality_status == "pass"
    assert result.meta.fetched_at is not None


@respx.mock(base_url=MOCK_BASE)
def test_provider_health(respx_mock):
    health_response = {"providers": [{"provider": "kbs", "status": "HEALTHY"}]}
    respx_mock.get("/v1/providers/health").mock(
        return_value=httpx.Response(200, json=health_response)
    )
    client = VnstockClient(base_url=MOCK_BASE)
    result = client.get_provider_health()
    assert len(result.providers) == 1
    assert result.providers[0]["provider"] == "kbs"


def test_no_provider_specific_logic():
    """vnalpha client MUST NOT import vnstock provider classes."""
    import inspect

    import vnalpha.clients.vnstock.client as mod

    src = inspect.getsource(mod)
    # Ensure no direct imports of vnstock provider internals
    assert "from vnstock.providers" not in src
    assert "from vnstock.explorer" not in src
    assert "PluginRegistry" not in src
