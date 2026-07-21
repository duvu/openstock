from __future__ import annotations

from unittest.mock import MagicMock

from vnalpha.data_provisioning.service import (
    DataProvisioningDependencies,
    DataProvisioningRequest,
    DataProvisioningService,
    ProvisioningStatus,
)
from vnalpha.ingestion.models import (
    BatchIngestionStatus,
    IngestionErrorCategory,
    IngestionRemediationAction,
    IngestionRemediationStep,
    OHLCVBatchResult,
    SymbolIngestionResult,
    SymbolIngestionStatus,
)


def _symbol_result(
    status: SymbolIngestionStatus,
    *,
    symbol: str = "FPT",
) -> SymbolIngestionResult:
    category = (
        IngestionErrorCategory.CONNECTION
        if status is SymbolIngestionStatus.FAILED
        else None
    )
    remediation_step = IngestionRemediationStep(
        action=(
            IngestionRemediationAction.RETRY_OHLCV
            if status is SymbolIngestionStatus.FAILED
            else IngestionRemediationAction.VERIFY_RANGE_AND_RETRY
        ),
        command=(
            "vnalpha",
            "data",
            "download",
            "ohlcv",
            symbol,
            "--start",
            "2026-07-01",
            "--end",
            "2026-07-10",
            "--source",
            "KBS",
        ),
        guidance="Retry the bounded command.",
    )
    return SymbolIngestionResult(
        symbol=symbol,
        status=status,
        requested_start="2026-07-01",
        requested_end="2026-07-10",
        provider="KBS",
        error_category=category,
        retryable=status is SymbolIngestionStatus.FAILED,
        message="Provider connection failed." if category else "No rows returned.",
        remediation=(
            "Retry with: vnalpha data download ohlcv "
            f"{symbol} --start 2026-07-01 --end 2026-07-10 --source KBS"
        ),
        remediation_steps=(remediation_step,),
        attempts=2 if category else 1,
    )


def test_provisioning_uses_explicit_failed_batch_status_and_preserves_symbols() -> None:
    batch = OHLCVBatchResult(
        run_id="ing-78",
        status=BatchIngestionStatus.FAILED,
        symbol_results=(_symbol_result(SymbolIngestionStatus.FAILED),),
        terminal_reason="no_required_symbol_completed",
    )
    service = DataProvisioningService(
        MagicMock(),
        dependencies=DataProvisioningDependencies(
            sync_ohlcv=MagicMock(return_value=batch)
        ),
    )

    result = service.execute(
        DataProvisioningRequest("download", "ohlcv", symbol="FPT", source="KBS")
    )

    assert result.status is ProvisioningStatus.FAILED
    assert result.counts["failed"] == 1
    assert result.symbol_results == batch.symbol_results
    assert result.terminal_reason == "no_required_symbol_completed"
    assert result.error == "No required OHLCV symbol completed."
    assert "FPT" in result.warnings[0]
    assert "vnalpha data download ohlcv FPT" in result.follow_up


def _unsupported_corporate_action_result() -> dict:
    return {
        "run_id": "run-unsupported",
        "status": "UNSUPPORTED",
        "error": "Provider does not support corporate actions.",
        "observed": 0,
        "raw_inserted": 0,
        "canonical_inserted": 0,
        "unchanged": 0,
        "revised": 0,
        "conflicts": 0,
        "quarantined": 0,
        "affected_ranges": 0,
    }
