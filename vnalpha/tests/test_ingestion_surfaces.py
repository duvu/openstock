from __future__ import annotations

import json
from unittest.mock import MagicMock

from typer.testing import CliRunner

from vnalpha.cli_app import data as data_cli
from vnalpha.cli_app import sync as sync_cli
from vnalpha.commands.handlers.data import handle_data
from vnalpha.commands.models import CommandResult, CommandStatus
from vnalpha.commands.parser import parse
from vnalpha.commands.registry import CommandMeta, CommandRegistry
from vnalpha.data_provisioning.service import (
    DataProvisioningDependencies,
    DataProvisioningRequest,
    DataProvisioningResult,
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
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


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


def test_data_cli_json_and_tui_payload_include_outcome_details() -> None:
    symbol_result = _symbol_result(SymbolIngestionStatus.EMPTY)
    result = DataProvisioningResult(
        status=ProvisioningStatus.FAILED,
        operation="download",
        artifact="ohlcv",
        correlation_id="corr-78",
        counts={"empty": 1},
        symbol="FPT",
        symbol_results=(symbol_result,),
        warnings=("FPT: EMPTY - No rows returned.",),
        follow_up=symbol_result.remediation,
        terminal_reason="no_required_symbol_completed",
    )

    rendered = json.loads(data_cli._render(result))
    service = MagicMock()
    service.execute.return_value = result
    tui_result = handle_data(
        parse("/data download ohlcv FPT --source KBS"),
        conn=MagicMock(),
        service=service,
    )

    assert rendered["symbol_results"][0]["status"] == "EMPTY"
    assert rendered["terminal_reason"] == "no_required_symbol_completed"
    assert rendered["symbol_results"][0]["remediation_steps"][0]["action"] == (
        "VERIFY_RANGE_AND_RETRY"
    )
    assert "vnalpha data download ohlcv FPT" in rendered["follow_up"]
    panel = tui_result.panels[0].content
    assert panel["symbol_results"][0]["symbol"] == "FPT"
    assert panel["terminal_reason"] == "no_required_symbol_completed"
    assert "vnalpha data download ohlcv FPT" in panel["follow_up"]


def test_legacy_sync_cli_lists_failed_and_empty_symbols(monkeypatch) -> None:
    failed = _symbol_result(SymbolIngestionStatus.FAILED, symbol="FPT")
    empty = _symbol_result(SymbolIngestionStatus.EMPTY, symbol="VNM")
    provisioning_result = DataProvisioningResult(
        status=ProvisioningStatus.PARTIAL,
        operation="download",
        artifact="ohlcv",
        correlation_id="corr-78",
        counts={"inserted": 3, "failed": 1, "empty": 1, "skipped": 0},
        symbol_results=(failed, empty),
        warnings=("FPT: FAILED", "VNM: EMPTY"),
        follow_up=failed.remediation,
    )

    class Service:
        def __init__(self, _conn):
            pass

        def execute(self, _request):
            return provisioning_result

    monkeypatch.setattr(sync_cli, "DataProvisioningService", Service)
    monkeypatch.setattr("vnalpha.warehouse.connection.get_connection", MagicMock())
    monkeypatch.setattr("vnalpha.warehouse.migrations.run_migrations", MagicMock())

    cli_result = CliRunner().invoke(sync_cli.app, ["ohlcv", "--symbols", "FPT,VNM"])

    assert cli_result.exit_code == 0
    assert "FPT: FAILED" in cli_result.output
    assert "VNM: EMPTY" in cli_result.output
    assert "vnalpha data download ohlcv FPT" in cli_result.output


def test_legacy_sync_cli_lists_all_failed_symbols_before_nonzero_exit(
    monkeypatch,
) -> None:
    failed = _symbol_result(SymbolIngestionStatus.FAILED, symbol="FPT")
    provisioning_result = DataProvisioningResult(
        status=ProvisioningStatus.FAILED,
        operation="download",
        artifact="ohlcv",
        correlation_id="corr-78-failed",
        counts={"inserted": 0, "failed": 1, "empty": 0, "skipped": 0},
        symbol_results=(failed,),
        warnings=("FPT: FAILED",),
        error="OHLCV sync did not complete.",
        follow_up=failed.remediation,
    )

    class Service:
        def __init__(self, _conn):
            pass

        def execute(self, _request):
            return provisioning_result

    monkeypatch.setattr(sync_cli, "DataProvisioningService", Service)
    monkeypatch.setattr("vnalpha.warehouse.connection.get_connection", MagicMock())
    monkeypatch.setattr("vnalpha.warehouse.migrations.run_migrations", MagicMock())

    cli_result = CliRunner().invoke(sync_cli.app, ["ohlcv", "--symbols", "FPT"])

    assert cli_result.exit_code == 1
    assert "FPT: FAILED" in cli_result.output
    assert "vnalpha data download ohlcv FPT" in cli_result.output


def test_legacy_sync_rejects_invalid_universe_before_opening_warehouse(
    monkeypatch,
) -> None:
    get_connection = MagicMock()
    run_migrations = MagicMock()
    monkeypatch.setattr("vnalpha.warehouse.connection.get_connection", get_connection)
    monkeypatch.setattr("vnalpha.warehouse.migrations.run_migrations", run_migrations)

    cli_result = CliRunner().invoke(
        sync_cli.app,
        ["ohlcv", "--universe", "NOT_A_REAL_UNIVERSE"],
    )

    assert cli_result.exit_code == 1
    assert "Unknown universe" in cli_result.output
    get_connection.assert_not_called()
    run_migrations.assert_not_called()


def test_tui_default_date_is_not_injected_into_bounded_data_download() -> None:
    from vnalpha.commands.executor import CommandExecutor

    captured_options: dict[str, str | bool] = {}

    def capture(parsed, **_kwargs):
        captured_options.update(parsed.options)
        return CommandResult(
            status=CommandStatus.SUCCESS,
            title="data",
            summary="captured",
        )

    registry = CommandRegistry()
    registry.register(
        CommandMeta(
            name="data",
            description="data",
            usage="/data",
            examples=[],
            permissions=[],
            handler=capture,
        )
    )
    conn = in_memory_connection()
    run_migrations(conn=conn)
    try:
        result = CommandExecutor(
            conn,
            surface="tui",
            registry=registry,
            default_date="2026-07-14",
        ).execute("/data download ohlcv FPT --start 2026-07-01 --end 2026-07-10")
    finally:
        conn.close()

    assert result.status is CommandStatus.SUCCESS
    assert captured_options == {"start": "2026-07-01", "end": "2026-07-10"}
