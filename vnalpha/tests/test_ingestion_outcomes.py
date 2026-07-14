from __future__ import annotations

from unittest.mock import MagicMock

import duckdb
import httpx
import pytest
import respx

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.clients.vnstock.errors import VnstockConnectionError, VnstockHTTPError
from vnalpha.clients.vnstock.schemas import OHLCVResponse
from vnalpha.ingestion.models import IngestionErrorCategory
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

    def fetch(*, symbol: str, **_kwargs):
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


def test_all_failed_batch_persists_failed_status(conn) -> None:
    client = MagicMock()
    client.get_equity_ohlcv.side_effect = VnstockConnectionError("offline")

    result = sync_ohlcv(conn, universe=["FPT", "VNM"], client=client)

    assert result["status"] == "FAILED"
    assert result["failed_symbols"] == ["FPT", "VNM"]
    persisted = conn.execute(
        "SELECT status FROM ingestion_run WHERE ingestion_run_id = ?",
        [result["run_id"]],
    ).fetchone()
    assert persisted == ("FAILED",)


def test_empty_response_remains_distinct_from_provider_failure(conn) -> None:
    client = MagicMock()
    client.get_equity_ohlcv.return_value = _response("FPT", rows=0)

    result = sync_ohlcv(conn, universe=["FPT"], client=client)

    symbol_result = result.symbol_results[0]
    assert result["status"] == "FAILED"
    assert symbol_result.status.value == "EMPTY"
    assert symbol_result.error_category is None
    assert result["empty_symbols"] == ["FPT"]
    assert result["failed_symbols"] == []


def test_provider_skipped_response_remains_distinct_from_empty(conn) -> None:
    payload = _response("FPT", rows=0).model_dump(mode="json")
    payload["meta"]["quality_status"] = "skipped"
    client = MagicMock()
    client.get_equity_ohlcv.return_value = OHLCVResponse.model_validate(payload)

    result = sync_ohlcv(conn, universe=["FPT"], client=client)

    symbol_result = result.symbol_results[0]
    assert result.status.value == "SUCCESS"
    assert symbol_result.status.value == "SKIPPED"
    assert symbol_result.error_category is None
    assert result["skipped_symbols"] == ["FPT"]
    assert result["empty_symbols"] == []


@respx.mock(base_url="http://127.0.0.1:6900")
def test_timeout_has_a_retryable_timeout_category(respx_mock, conn) -> None:
    respx_mock.get("/v1/equity/ohlcv").mock(
        side_effect=httpx.ReadTimeout("provider timed out")
    )
    client = VnstockClient(base_url="http://127.0.0.1:6900")

    try:
        result = sync_ohlcv(conn, universe=["FPT"], client=client)
    finally:
        client.close()

    symbol_result = result.symbol_results[0]
    assert symbol_result.status.value == "FAILED"
    assert symbol_result.error_category is not None
    assert symbol_result.error_category.value == "TIMEOUT"
    assert symbol_result.retryable is True
    assert symbol_result.attempts == 2
    assert symbol_result.diagnostics_ref == f"ingestion:{result.run_id}:FPT"


def test_contract_failure_is_invalid_provider_data(conn) -> None:
    client = MagicMock()
    client.get_equity_ohlcv.side_effect = VnstockHTTPError(
        422,
        "/v1/equity/ohlcv",
        '{"error":"contract_validation_failed","request_id":"req-invalid"}',
    )

    result = sync_ohlcv(conn, universe=["FPT"], client=client)

    symbol_result = result.symbol_results[0]
    assert symbol_result.status.value == "INVALID"
    assert symbol_result.error_category is not None
    assert symbol_result.error_category.value == "PROVIDER_DATA"
    assert symbol_result.retryable is False


@respx.mock(base_url="http://127.0.0.1:6900")
def test_malformed_ohlcv_record_is_invalid_not_success(respx_mock, conn) -> None:
    respx_mock.get("/v1/equity/ohlcv").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [{"symbol": "FPT", "close": 101.0}],
                "meta": {"dataset": "equity.ohlcv", "provider": "KBS"},
                "diagnostics": {},
            },
        )
    )
    client = VnstockClient(base_url="http://127.0.0.1:6900")

    try:
        result = sync_ohlcv(conn, universe=["FPT"], client=client)
    finally:
        client.close()

    symbol_result = result.symbol_results[0]
    assert symbol_result.status.value == "INVALID"
    assert symbol_result.error_category is not None
    assert symbol_result.error_category.value == "INVALID_DATA"


@respx.mock(base_url="http://127.0.0.1:6900")
def test_invalid_timestamp_is_invalid_not_success(respx_mock, conn) -> None:
    respx_mock.get("/v1/equity/ohlcv").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "symbol": "FPT",
                        "time": "not-a-date",
                        "open": 100.0,
                        "high": 102.0,
                        "low": 99.0,
                        "close": 101.0,
                    }
                ],
                "meta": {"dataset": "equity.ohlcv", "provider": "KBS"},
                "diagnostics": {},
            },
        )
    )
    client = VnstockClient(base_url="http://127.0.0.1:6900")

    try:
        result = sync_ohlcv(conn, universe=["FPT"], client=client)
    finally:
        client.close()

    symbol_result = result.symbol_results[0]
    assert symbol_result.status.value == "INVALID"
    assert symbol_result.error_category is IngestionErrorCategory.INVALID_DATA


@respx.mock(base_url="http://127.0.0.1:6900")
def test_invalid_json_has_its_own_category(respx_mock, conn) -> None:
    respx_mock.get("/v1/equity/ohlcv").mock(
        return_value=httpx.Response(200, text="not-json")
    )
    client = VnstockClient(base_url="http://127.0.0.1:6900")

    try:
        result = sync_ohlcv(conn, universe=["FPT"], client=client)
    finally:
        client.close()

    symbol_result = result.symbol_results[0]
    assert symbol_result.status.value == "INVALID"
    assert symbol_result.error_category is not None
    assert symbol_result.error_category.value == "INVALID_JSON"


def test_retryable_failure_can_succeed_on_the_bounded_retry(conn) -> None:
    client = MagicMock()
    client.get_equity_ohlcv.side_effect = [
        VnstockConnectionError("offline"),
        _response("FPT", rows=1),
    ]

    result = sync_ohlcv(conn, universe=["FPT"], client=client)

    symbol_result = result.symbol_results[0]
    assert result["status"] == "SUCCESS"
    assert symbol_result.status.value == "SUCCESS"
    assert symbol_result.attempts == 2
    assert client.get_equity_ohlcv.call_count == 2
    assert result.get("inserted", 0) == 1


def test_storage_failure_is_a_failed_symbol_not_a_batch_exception(
    conn, monkeypatch
) -> None:
    client = MagicMock()
    client.get_equity_ohlcv.return_value = _response("FPT", rows=1)
    monkeypatch.setattr(
        "vnalpha.ingestion.symbol_sync.insert_raw_ohlcv",
        MagicMock(side_effect=duckdb.Error("storage unavailable")),
    )

    result = sync_ohlcv(conn, universe=["FPT"], client=client)

    symbol_result = result.symbol_results[0]
    assert result.status.value == "FAILED"
    assert symbol_result.status.value == "FAILED"
    assert symbol_result.error_category is not None
    assert symbol_result.error_category.value == "STORAGE"
    assert symbol_result.retryable is False
