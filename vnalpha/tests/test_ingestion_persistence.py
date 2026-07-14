from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vnalpha.clients.vnstock.schemas import OHLCVResponse
from vnalpha.ingestion.models import IngestionErrorCategory
from vnalpha.ingestion.sync_ohlcv import sync_ohlcv
from vnalpha.observability.context import set_correlation_id
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn():
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _response(*, quality_status: str = "PASS") -> OHLCVResponse:
    return OHLCVResponse.model_validate(
        {
            "data": [
                {
                    "symbol": "FPT",
                    "time": "2026-07-01 00:00:00",
                    "interval": "1D",
                    "open": 100.0,
                    "high": 102.0,
                    "low": 99.0,
                    "close": 101.0,
                    "volume": 1000.0,
                }
            ],
            "meta": {
                "request_id": "req-quality",
                "dataset": "equity.ohlcv",
                "provider": "KBS",
                "quality_status": quality_status,
            },
            "diagnostics": {
                "quality": {"valid": quality_status == "PASS", "checks": ["ohlc"]},
                "routing": {"selected": "KBS"},
            },
        }
    )


def test_quality_and_diagnostics_are_persisted_with_raw_rows(conn) -> None:
    client = MagicMock()
    client.get_equity_ohlcv.return_value = _response()

    result = sync_ohlcv(conn, universe=["FPT"], client=client)

    raw_metadata = conn.execute(
        "SELECT quality_report_json, diagnostics_json "
        "FROM market_ohlcv_raw "
        "WHERE ingestion_run_id = ? AND symbol = 'FPT'",
        [result["run_id"]],
    ).fetchone()
    assert raw_metadata is not None
    assert '"valid": true' in raw_metadata[0]
    assert '"selected": "KBS"' in raw_metadata[1]
    run_metadata = conn.execute(
        "SELECT quality_report_json, diagnostics_json FROM ingestion_run "
        "WHERE ingestion_run_id = ?",
        [result["run_id"]],
    ).fetchone()
    assert run_metadata is not None
    assert '"valid": true' in run_metadata[0]
    assert '"selected": "KBS"' in run_metadata[1]


def test_failed_provider_quality_is_invalid_even_when_raw_rows_exist(conn) -> None:
    client = MagicMock()
    client.get_equity_ohlcv.return_value = _response(quality_status="FAIL")

    result = sync_ohlcv(conn, universe=["FPT"], client=client)

    symbol_result = result.symbol_results[0]
    assert result.status.value == "FAILED"
    assert symbol_result.status.value == "INVALID"
    assert symbol_result.error_category is IngestionErrorCategory.PROVIDER_DATA
    assert symbol_result.rows_inserted == 1


def test_ingestion_run_persists_truthful_summary_and_symbol_results(conn) -> None:
    correlation_id = set_correlation_id()
    response = _response().model_copy(update={"data": []})
    client = MagicMock()
    client.get_equity_ohlcv.return_value = response

    result = sync_ohlcv(conn, universe=["FPT"], client=client)

    persisted = conn.execute(
        "SELECT requested_count, success_count, empty_count, failed_count, "
        "invalid_count, skipped_count, terminal_reason, symbol_results_json, "
        "correlation_id FROM ingestion_run WHERE ingestion_run_id = ?",
        [result["run_id"]],
    ).fetchone()
    assert persisted is not None
    assert persisted[:6] == (1, 0, 1, 0, 0, 0)
    assert persisted[6] == "no_required_symbol_completed"
    assert '"status": "EMPTY"' in persisted[7]
    assert persisted[8] == correlation_id
