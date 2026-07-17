from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vnalpha.clients.vnstock.schemas import OHLCVResponse
from vnalpha.ingestion.models import IngestionErrorCategory
from vnalpha.ingestion.sync_index import sync_index_ohlcv
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


def test_fiinquantx_safe_lineage_excludes_activation_identifiers(
    conn, monkeypatch
) -> None:
    monkeypatch.setenv("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED", "true")
    response = _response(provider="FIINQUANTX").model_copy(
        update={
            "meta": _response(provider="FIINQUANTX").meta.model_copy(
                update={
                    "quality_report": {
                        "valid": True,
                        "FIINQUANT_PASSWORD": "quality-secret",
                    }
                }
            ),
            "diagnostics": {
                "provider_lineage": {
                    "sdk_version": "0.1.64",
                    "contract_version": "fiinquantx-contract-v1",
                    "source_method": "Fetch_Trading_Data",
                    "ohlcv_request_policy": {"basis": "RAW_UNADJUSTED"},
                }
            },
        }
    )
    client = MagicMock()
    client.get_equity_ohlcv.return_value = response

    result = sync_ohlcv(
        conn,
        universe=["FPT"],
        source="FIINQUANTX",
        client=client,
    )

    diagnostics_json = conn.execute(
        "SELECT diagnostics_json FROM market_ohlcv_raw "
        "WHERE ingestion_run_id = ? AND symbol = 'FPT'",
        [result.run_id],
    ).fetchone()[0]
    assert '"basis": "RAW_UNADJUSTED"' in diagnostics_json
    assert "approval_reference" not in diagnostics_json
    assert "approval_fingerprint" not in diagnostics_json
    assert "quality-secret" not in str(
        conn.execute(
            "SELECT quality_report_json FROM market_ohlcv_raw "
            "WHERE ingestion_run_id = ? AND symbol = 'FPT'",
            [result.run_id],
        ).fetchone()[0]
    )


def test_equity_raw_rows_roll_back_when_metadata_persistence_fails(
    conn, monkeypatch
) -> None:
    client = MagicMock()
    client.get_equity_ohlcv.return_value = _response()
    from vnalpha.ingestion import symbol_sync as symbol_sync_module

    def fail_metadata(*_args, **_kwargs) -> None:
        raise RuntimeError("metadata persistence failed")

    monkeypatch.setattr(
        symbol_sync_module,
        "persist_raw_ohlcv_metadata",
        fail_metadata,
    )

    with pytest.raises(RuntimeError, match="metadata persistence failed"):
        sync_ohlcv(conn, universe=["FPT"], client=client)

    assert conn.execute("SELECT count(*) FROM market_ohlcv_raw").fetchone() == (0,)
    assert conn.execute("SELECT status FROM ingestion_run").fetchone() == ("FAILED",)


def test_fiinquantx_index_sync_persists_correlation_and_safe_lineage(
    conn, monkeypatch
) -> None:
    monkeypatch.setenv("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED", "true")
    correlation_id = set_correlation_id()
    response = _response(provider="FIINQUANTX").model_copy(
        update={
            "data": [
                {
                    "symbol": "VNINDEX",
                    "time": "2026-07-01 00:00:00",
                    "interval": "1D",
                    "open": 100.0,
                    "high": 102.0,
                    "low": 99.0,
                    "close": 101.0,
                    "volume": 1000.0,
                }
            ],
            "meta": _response(provider="FIINQUANTX").meta.model_copy(
                update={"dataset": "index.ohlcv"}
            ),
            "diagnostics": {
                "provider_lineage": {
                    "sdk_version": "0.1.64",
                    "contract_version": "fiinquantx-contract-v1",
                    "source_method": "Fetch_Trading_Data",
                    "ohlcv_request_policy": {
                        "adjusted": "requested_false",
                        "basis": "RAW_UNADJUSTED",
                    },
                    "password": "must-not-persist",
                },
                "password": "must-not-persist",
            },
        }
    )
    client = MagicMock()
    client.get_index_ohlcv.return_value = response

    result = sync_index_ohlcv(
        conn,
        source="FIINQUANTX",
        client=client,
    )

    raw = conn.execute(
        "SELECT diagnostics_json FROM market_ohlcv_raw "
        "WHERE ingestion_run_id = ? AND symbol = 'VNINDEX'",
        [result["run_id"]],
    ).fetchone()[0]
    run = conn.execute(
        "SELECT correlation_id FROM ingestion_run WHERE ingestion_run_id = ?",
        [result["run_id"]],
    ).fetchone()
    assert '"basis": "RAW_UNADJUSTED"' in raw
    assert "approval_reference" not in raw
    assert "approval_fingerprint" not in raw
    assert "password" not in raw
    assert run == (correlation_id,)


def test_fiinquantx_index_policy_rejects_before_run_creation(conn) -> None:
    with pytest.raises(ValueError, match="FIINQUANTX persistence is disabled"):
        sync_index_ohlcv(conn, source="FIINQUANTX", client=MagicMock())

    assert conn.execute("SELECT count(*) FROM ingestion_run").fetchone()[0] == 0


def test_index_missing_provider_quality_fails_without_raw_persistence(conn) -> None:
    response = _response(quality_status=None).model_copy(
        update={
            "meta": _response(quality_status=None).meta.model_copy(
                update={"dataset": "index.ohlcv"}
            )
        }
    )
    client = MagicMock()
    client.get_index_ohlcv.return_value = response

    with pytest.raises(ValueError, match="quality"):
        sync_index_ohlcv(conn, client=client)

    assert conn.execute("SELECT count(*) FROM market_ohlcv_raw").fetchone() == (0,)
    assert conn.execute("SELECT status FROM ingestion_run").fetchone() == ("FAILED",)


def test_index_terminal_update_failure_rolls_back_raw_rows(conn, monkeypatch) -> None:
    response = _response().model_copy(
        update={"meta": _response().meta.model_copy(update={"dataset": "index.ohlcv"})}
    )
    client = MagicMock()
    client.get_index_ohlcv.return_value = response
    from vnalpha.ingestion import sync_index as sync_index_module

    original = sync_index_module.finish_ingestion_run

    def fail_success(connection, run_id, status, **kwargs):
        if status != "FAILED":
            raise RuntimeError("terminal update failed")
        return original(connection, run_id, status, **kwargs)

    monkeypatch.setattr(sync_index_module, "finish_ingestion_run", fail_success)

    with pytest.raises(RuntimeError, match="terminal update failed"):
        sync_index_ohlcv(conn, client=client)

    assert conn.execute("SELECT count(*) FROM market_ohlcv_raw").fetchone() == (0,)
    assert conn.execute("SELECT status FROM ingestion_run").fetchone() == ("FAILED",)


@pytest.mark.parametrize("basis", [None, "ADJUSTED"])
def test_fiinquantx_non_raw_basis_is_rejected_before_raw_persistence(
    conn, monkeypatch, basis
) -> None:
    monkeypatch.setenv("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED", "true")
    response = _response(provider="FIINQUANTX").model_copy(
        update={
            "diagnostics": {
                "provider_lineage": {
                    "ohlcv_request_policy": {"basis": basis},
                }
            }
        }
    )
    client = MagicMock()
    client.get_equity_ohlcv.return_value = response

    with pytest.raises(ValueError, match="RAW_UNADJUSTED"):
        sync_ohlcv(
            conn,
            universe=["FPT"],
            source="FIINQUANTX",
            client=client,
        )

    assert conn.execute("SELECT count(*) FROM market_ohlcv_raw").fetchone() == (0,)


def test_implicit_fiinquantx_response_requires_persistence_approval(
    conn, monkeypatch
) -> None:
    monkeypatch.delenv("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED", raising=False)
    client = MagicMock()
    client.get_equity_ohlcv.return_value = _response(provider="FIINQUANTX")

    with pytest.raises(ValueError, match="FIINQUANTX persistence is disabled"):
        sync_ohlcv(conn, universe=["FPT"], client=client)

    assert conn.execute("SELECT count(*) FROM market_ohlcv_raw").fetchone() == (0,)


def test_failed_provider_quality_is_invalid_even_when_raw_rows_exist(conn) -> None:
    client = MagicMock()
    client.get_equity_ohlcv.return_value = _response(quality_status="FAIL")

    result = sync_ohlcv(conn, universe=["FPT"], client=client)

    symbol_result = result.symbol_results[0]
    assert result.status.value == "FAILED"
    assert symbol_result.status.value == "INVALID"
    assert symbol_result.error_category is IngestionErrorCategory.PROVIDER_DATA
    assert symbol_result.rows_inserted == 1


def test_missing_provider_quality_is_invalid_without_raw_persistence(conn) -> None:
    client = MagicMock()
    client.get_equity_ohlcv.return_value = _response(quality_status=None)

    result = sync_ohlcv(conn, universe=["FPT"], client=client)

    symbol_result = result.symbol_results[0]
    assert symbol_result.status.value == "INVALID"
    assert symbol_result.rows_inserted == 0
    assert conn.execute("SELECT count(*) FROM market_ohlcv_raw").fetchone() == (0,)


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
