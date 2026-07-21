from __future__ import annotations

from unittest.mock import MagicMock

import pytest

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


def _response(
    *, quality_status: str | None = "PASS", provider: str = "KBS"
) -> OHLCVResponse:
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
                "provider": provider,
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
