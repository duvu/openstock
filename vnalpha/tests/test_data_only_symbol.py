from __future__ import annotations

import pytest

import vnalpha.data_provisioning.data_only_symbol as data_only_symbol
from vnalpha.data_provisioning.service import (
    DataProvisioningRequest,
    DataProvisioningResult,
    ProvisioningStatus,
)
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import create_ingestion_run


def test_raw_ready_canonical_stale_promotes_only_the_missing_tail() -> None:
    connection = in_memory_connection()
    run_migrations(conn=connection, emit_observability=False)
    connection.execute("INSERT INTO symbol_master (symbol) VALUES ('FPT')")
    run_id = create_ingestion_run(connection, "fixture", "/ohlcv")
    connection.executemany(
        "INSERT INTO market_ohlcv_raw "
        "(ingestion_run_id, symbol, time, interval, open, high, low, close, "
        "volume, provider, price_basis, quality_status) "
        "VALUES (?, 'FPT', ?, '1D', 10, 11, 9, ?, 1000, 'fixture', "
        "'RAW_UNADJUSTED', 'pass')",
        [(run_id, "2026-01-05", 10.0), (run_id, "2026-01-06", 11.0)],
    )
    connection.execute(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, open, high, low, close, volume, "
        "selected_provider, quality_status) "
        "VALUES ('FPT', '2026-01-05', '1D', 10, 11, 9, 10, 1000, "
        "'fixture', 'pass')"
    )

    result = data_only_symbol.provision_data_only_symbol(
        connection,
        "FPT",
        "2026-01-06",
        refresh=False,
        correlation_id="test-correlation",
    )

    rows = connection.execute(
        "SELECT CAST(time AS DATE)::VARCHAR FROM canonical_ohlcv "
        "WHERE symbol = 'FPT' ORDER BY time"
    ).fetchall()
    connection.close()
    assert [action.action for action in result.actions] == ["build_canonical"]
    assert result.actions[0].to_dict() == {
        "action": "build_canonical",
        "status": "SUCCESS",
        "dataset": "equity.ohlcv",
        "symbol": "FPT",
        "start_date": "2026-01-06",
        "end_date": "2026-01-06",
        "source": "fixture",
        "ingestion_run_id": run_id,
    }
    assert rows == [("2026-01-05",), ("2026-01-06",)]


def test_stale_raw_evidence_syncs_only_the_missing_session_tail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = in_memory_connection()
    run_migrations(conn=connection, emit_observability=False)
    connection.execute("INSERT INTO symbol_master (symbol) VALUES ('FPT')")
    run_id = create_ingestion_run(connection, "fixture", "/ohlcv")
    connection.execute(
        "INSERT INTO market_ohlcv_raw "
        "(ingestion_run_id, symbol, time, interval, open, high, low, close, "
        "volume, provider, price_basis, quality_status) "
        "VALUES (?, 'FPT', '2026-01-05', '1D', 10, 11, 9, 10, 1000, "
        "'fixture', 'RAW_UNADJUSTED', 'pass')",
        [run_id],
    )
    connection.execute(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, open, high, low, close, volume, "
        "selected_provider, quality_status) "
        "VALUES ('FPT', '2026-01-07', '1D', 10, 11, 9, 10, 1000, "
        "'fixture', 'pass')"
    )
    requests: list[DataProvisioningRequest] = []

    class RecordingProvisioner:
        def __init__(self, _connection: object) -> None:
            pass

        def execute(self, request: DataProvisioningRequest) -> DataProvisioningResult:
            requests.append(request)
            return DataProvisioningResult(
                status=ProvisioningStatus.SUCCESS,
                operation=request.operation,
                artifact=request.artifact,
                correlation_id="test-correlation",
            )

    monkeypatch.setattr(
        data_only_symbol, "DataProvisioningService", RecordingProvisioner
    )
    canonical_ranges: list[tuple[str | None, str | None]] = []

    def record_canonical(
        _connection, *, symbol: str, start: str | None, end: str | None
    ) -> dict[str, int]:
        assert symbol == "FPT"
        canonical_ranges.append((start, end))
        return {"upserted": 1, "rejected": 0}

    monkeypatch.setattr(data_only_symbol, "build_canonical_ohlcv", record_canonical)

    result = data_only_symbol.provision_data_only_symbol(
        connection,
        "FPT",
        "2026-01-07",
        refresh=False,
        correlation_id="test-correlation",
    )
    refreshed = data_only_symbol.provision_data_only_symbol(
        connection,
        "FPT",
        "2026-01-07",
        refresh=True,
        correlation_id="test-correlation",
    )
    monkeypatch.setattr(
        data_only_symbol,
        "build_canonical_ohlcv",
        lambda *_args, **_kwargs: {"upserted": 0, "rejected": 0},
    )
    empty_publication = data_only_symbol.provision_data_only_symbol(
        connection,
        "FPT",
        "2026-01-07",
        refresh=True,
        correlation_id="test-correlation",
    )
    connection.close()

    assert [(request.start, request.end) for request in requests] == [
        ("2026-01-06", "2026-01-07"),
        ("2026-01-07", "2026-01-07"),
        ("2026-01-07", "2026-01-07"),
    ]
    assert [action.to_dict() for action in result.actions] == [
        {
            "action": "sync_ohlcv",
            "status": "SUCCESS",
            "dataset": "equity.ohlcv",
            "symbol": "FPT",
            "start_date": "2026-01-06",
            "end_date": "2026-01-07",
        },
        {"action": "reuse_fresh", "status": "SUCCESS"},
    ]
    assert canonical_ranges == [("2026-01-07", "2026-01-07")]
    assert refreshed.refreshed is True
    assert empty_publication.errors == (
        "Canonical OHLCV build did not produce persisted rows.",
    )
    assert empty_publication.actions[-1].to_dict() == {
        "action": "build_canonical",
        "status": "FAILED",
        "dataset": "equity.ohlcv",
        "symbol": "FPT",
        "failure_category": "CANONICAL_ROWS_MISSING",
        "start_date": "2026-01-07",
        "end_date": "2026-01-07",
        "source": "fixture",
    }
