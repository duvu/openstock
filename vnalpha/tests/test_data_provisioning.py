from __future__ import annotations

from unittest.mock import MagicMock


def test_download_ohlcv_normalizes_arguments_and_reports_operation_evidence() -> None:
    from vnalpha.data_provisioning.service import (
        DataProvisioningDependencies,
        DataProvisioningRequest,
        DataProvisioningService,
        ProvisioningStatus,
    )
    from vnalpha.ingestion.models import (
        BatchIngestionStatus,
        OHLCVBatchResult,
        SymbolIngestionResult,
        SymbolIngestionStatus,
    )

    sync_ohlcv = MagicMock(
        return_value=OHLCVBatchResult(
            run_id="ing-77",
            status=BatchIngestionStatus.PARTIAL,
            symbol_results=(
                SymbolIngestionResult(
                    symbol="FPT",
                    status=SymbolIngestionStatus.SUCCESS,
                    requested_start="2026-07-01",
                    requested_end="2026-07-10",
                    provider="KBS",
                    rows_received=4,
                    rows_inserted=4,
                ),
                SymbolIngestionResult(
                    symbol="VNM",
                    status=SymbolIngestionStatus.EMPTY,
                    requested_start="2026-07-01",
                    requested_end="2026-07-10",
                    provider="KBS",
                ),
            ),
            terminal_reason="mixed_symbol_outcomes",
        )
    )
    service = DataProvisioningService(
        MagicMock(),
        dependencies=DataProvisioningDependencies(sync_ohlcv=sync_ohlcv),
    )

    result = service.execute(
        DataProvisioningRequest(
            operation="download",
            artifact="ohlcv",
            symbol=" fpt ",
            start="2026-07-01",
            end="2026-07-10",
            source="KBS",
            interval="1H",
        )
    )

    assert result.status is ProvisioningStatus.PARTIAL
    assert result.artifact == "ohlcv"
    assert result.counts == {
        "total": 2,
        "requested": 2,
        "inserted": 4,
        "success": 1,
        "empty": 1,
        "failed": 0,
        "invalid": 0,
        "skipped": 0,
    }
    assert result.freshness == "bounded_range"
    assert result.lineage["ingestion_run_id"] == "ing-77"
    assert result.correlation_id
    sync_ohlcv.assert_called_once_with(
        service.conn,
        universe=["FPT"],
        start="2026-07-01",
        end="2026-07-10",
        source="KBS",
        interval="1H",
    )
