from __future__ import annotations

import json
from unittest.mock import MagicMock

import duckdb
import httpx
import pytest
import respx

from vnalpha.cli_app.data import _render
from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.clients.vnstock.errors import (
    VnstockConnectionError,
    VnstockHTTPError,
    VnstockTimeoutError,
)
from vnalpha.commands.handlers.data import handle_data
from vnalpha.commands.parser import parse
from vnalpha.data_provisioning.service import (
    DataProvisioningResult,
    ProvisioningStatus,
)
from vnalpha.ingestion.models import (
    IngestionErrorCategory,
    SymbolIngestionStatus,
)
from vnalpha.ingestion.sync_ohlcv import sync_ohlcv
from vnalpha.warehouse.migrations import run_migrations

_BASE_URL = "http://127.0.0.1:6923"


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _service_error() -> dict[str, object]:
    return {
        "error": "no_healthy_provider",
        "message": "Authorization: Bearer must-not-leak",
        "dataset": "equity.ohlcv",
        "candidates": ["KBS", "VCI"],
        "request_id": "req-diagnostics-232",
        "authorization": "Bearer must-not-leak",
    }


@respx.mock(base_url=_BASE_URL)
def test_http_error_parses_allowlisted_service_diagnostics_without_public_body(
    respx_mock,
) -> None:
    # Given: vnstock-service returns a typed error with hostile credential text.
    respx_mock.get("/v1/equity/ohlcv").mock(
        return_value=httpx.Response(503, json=_service_error())
    )

    # When: the HTTP client crosses the response boundary.
    with VnstockClient(base_url=_BASE_URL) as client:
        with pytest.raises(VnstockHTTPError) as captured:
            client.get_equity_ohlcv("FPT")

    # Then: stable fields survive while opaque response text stays non-public.
    error = captured.value
    assert error.status_code == 503
    assert error.service_error_code == "no_healthy_provider"
    assert error.request_id == "req-diagnostics-232"
    assert error.dataset == "equity.ohlcv"
    assert error.provider_candidates == ("KBS", "VCI")
    assert "must-not-leak" not in str(error)


def test_terminal_symbol_result_persists_typed_http_diagnostics_without_secret(
    conn,
) -> None:
    # Given: both bounded attempts receive the same typed service failure.
    client = MagicMock()
    client.get_equity_ohlcv.side_effect = VnstockHTTPError(
        503,
        "/v1/equity/ohlcv",
        json.dumps(_service_error()),
    )

    # When: OHLCV ingestion reaches a terminal result.
    result = sync_ohlcv(conn, universe=["FPT"], client=client)

    # Then: diagnostics remain distinguishable, bounded, persisted, and public-safe.
    symbol_result = result.symbol_results[0]
    assert symbol_result.message == "Provider HTTP request failed."
    assert symbol_result.diagnostics == {
        "http_status": 503,
        "service_error_code": "no_healthy_provider",
        "request_id": "req-diagnostics-232",
        "dataset": "equity.ohlcv",
        "source_requested": "auto",
        "provider_candidates": ["KBS", "VCI"],
        "retryable": True,
    }
    persisted = conn.execute(
        "SELECT symbol_results_json FROM ingestion_run WHERE ingestion_run_id = ?",
        [result.run_id],
    ).fetchone()
    assert persisted is not None
    assert "req-diagnostics-232" in persisted[0]
    assert "must-not-leak" not in persisted[0]


@pytest.mark.parametrize(
    ("status", "code", "retryable", "expected_status", "category", "attempts"),
    (
        (
            503,
            "no_healthy_provider",
            True,
            SymbolIngestionStatus.FAILED,
            IngestionErrorCategory.HTTP,
            2,
        ),
        (
            502,
            "provider_fetch_failed",
            True,
            SymbolIngestionStatus.FAILED,
            IngestionErrorCategory.HTTP,
            2,
        ),
        (
            422,
            "contract_validation_failed",
            False,
            SymbolIngestionStatus.INVALID,
            IngestionErrorCategory.PROVIDER_DATA,
            1,
        ),
        (
            400,
            "invalid_request",
            False,
            SymbolIngestionStatus.FAILED,
            IngestionErrorCategory.HTTP,
            1,
        ),
    ),
)
def test_service_failure_classes_remain_distinguishable_at_symbol_boundary(
    conn,
    status,
    code,
    retryable,
    expected_status,
    category,
    attempts,
) -> None:
    payload = {
        "error": code,
        "request_id": f"req-{code}",
        "dataset": "equity.ohlcv",
        "provider": "KBS",
        "provider_error_code": f"provider-{code}",
        "retryable": retryable,
        "secret": "must-not-leak",
    }
    client = MagicMock()
    client.get_equity_ohlcv.side_effect = VnstockHTTPError(
        status,
        "/v1/equity/ohlcv",
        json.dumps(payload),
    )

    symbol_result = sync_ohlcv(conn, universe=["FPT"], client=client).symbol_results[0]

    assert symbol_result.status is expected_status
    assert symbol_result.error_category is category
    assert symbol_result.retryable is retryable
    assert symbol_result.attempts == attempts
    assert symbol_result.diagnostics["http_status"] == status
    assert symbol_result.diagnostics["service_error_code"] == code
    assert symbol_result.diagnostics["request_id"] == f"req-{code}"
    assert "must-not-leak" not in json.dumps(symbol_result.to_payload())


@pytest.mark.parametrize(
    ("failure", "category", "message"),
    (
        (
            VnstockConnectionError("secret endpoint"),
            IngestionErrorCategory.CONNECTION,
            "Provider connection failed.",
        ),
        (
            VnstockTimeoutError("secret endpoint"),
            IngestionErrorCategory.TIMEOUT,
            "Provider request timed out.",
        ),
    ),
)
def test_transport_failures_remain_typed_and_public_safe(
    conn,
    failure,
    category,
    message,
) -> None:
    client = MagicMock()
    client.get_equity_ohlcv.side_effect = failure

    symbol_result = sync_ohlcv(conn, universe=["FPT"], client=client).symbol_results[0]

    assert symbol_result.status is SymbolIngestionStatus.FAILED
    assert symbol_result.error_category is category
    assert symbol_result.retryable is True
    assert symbol_result.attempts == 2
    assert symbol_result.message == message
    assert "secret endpoint" not in json.dumps(symbol_result.to_payload())


def test_provider_diagnostics_render_unchanged_at_cli_and_tui_boundaries(conn) -> None:
    client = MagicMock()
    client.get_equity_ohlcv.side_effect = VnstockHTTPError(
        503,
        "/v1/equity/ohlcv",
        json.dumps(_service_error()),
    )
    symbol_result = sync_ohlcv(conn, universe=["FPT"], client=client).symbol_results[0]
    provisioning = DataProvisioningResult(
        status=ProvisioningStatus.FAILED,
        operation="download",
        artifact="ohlcv",
        correlation_id="corr-boundary-232",
        symbol="FPT",
        symbol_results=(symbol_result,),
        error="Data provisioning did not complete.",
    )
    service = MagicMock()
    service.execute.return_value = provisioning

    cli_payload = json.loads(_render(provisioning))
    tui_result = handle_data(
        parse("/data download ohlcv FPT"), conn=conn, service=service
    )
    tui_payload = tui_result.panels[0].content

    for payload in (cli_payload, tui_payload):
        diagnostics = payload["symbol_results"][0]["diagnostics"]
        assert diagnostics["service_error_code"] == "no_healthy_provider"
        assert diagnostics["request_id"] == "req-diagnostics-232"
        assert "must-not-leak" not in json.dumps(payload)
