from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from vnalpha.cli import app
from vnalpha.commands.parser import parse


def test_download_ohlcv_normalizes_arguments_and_reports_operation_evidence() -> None:
    from vnalpha.data_provisioning.service import (
        DataProvisioningDependencies,
        DataProvisioningRequest,
        DataProvisioningService,
        ProvisioningStatus,
    )

    sync_ohlcv = MagicMock(return_value={"inserted": 4, "skipped": 1})
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
            source="vndirect",
            interval="1H",
        )
    )

    assert result.status is ProvisioningStatus.SUCCESS
    assert result.artifact == "ohlcv"
    assert result.counts == {"inserted": 4, "skipped": 1}
    assert result.correlation_id
    sync_ohlcv.assert_called_once_with(
        service.conn,
        universe=["FPT"],
        start="2026-07-01",
        end="2026-07-10",
        source="vndirect",
        interval="1H",
    )


def test_invalid_download_is_rejected_before_any_provider_adapter_runs() -> None:
    from vnalpha.data_provisioning.service import (
        DataProvisioningDependencies,
        DataProvisioningRequest,
        DataProvisioningService,
        DataProvisioningValidationError,
    )

    sync_ohlcv = MagicMock()
    service = DataProvisioningService(
        MagicMock(),
        dependencies=DataProvisioningDependencies(sync_ohlcv=sync_ohlcv),
    )

    with pytest.raises(DataProvisioningValidationError, match="requires a symbol"):
        service.execute(DataProvisioningRequest(operation="download", artifact="ohlcv"))

    sync_ohlcv.assert_not_called()


def test_unapproved_source_is_rejected_before_provider_adapter_runs() -> None:
    from vnalpha.data_provisioning.service import (
        DataProvisioningDependencies,
        DataProvisioningRequest,
        DataProvisioningService,
        DataProvisioningValidationError,
    )

    sync_ohlcv = MagicMock()
    service = DataProvisioningService(
        MagicMock(), dependencies=DataProvisioningDependencies(sync_ohlcv=sync_ohlcv)
    )
    with pytest.raises(DataProvisioningValidationError, match="source"):
        service.execute(
            DataProvisioningRequest("download", "ohlcv", symbol="FPT", source="NOT_APPROVED")
        )
    sync_ohlcv.assert_not_called()


def test_canonical_requires_symbol_before_builder_runs() -> None:
    from vnalpha.data_provisioning.service import (
        DataProvisioningDependencies,
        DataProvisioningRequest,
        DataProvisioningService,
        DataProvisioningValidationError,
    )

    builder = MagicMock()
    service = DataProvisioningService(
        MagicMock(), dependencies=DataProvisioningDependencies(build_canonical=builder)
    )
    with pytest.raises(DataProvisioningValidationError, match="canonical requires a symbol"):
        service.execute(DataProvisioningRequest("build", "canonical"))
    builder.assert_not_called()


def test_features_forwards_benchmark_symbol() -> None:
    from vnalpha.data_provisioning.service import (
        DataProvisioningDependencies,
        DataProvisioningRequest,
        DataProvisioningService,
    )

    builder = MagicMock(return_value={"built": 1, "skipped": 0})
    service = DataProvisioningService(
        MagicMock(), dependencies=DataProvisioningDependencies(build_features=builder)
    )
    service.execute(
        DataProvisioningRequest(
            "build", "features", symbol="FPT", date="2026-07-10", benchmark="CUSTOM"
        )
    )
    assert builder.call_args.kwargs["benchmark_symbol"] == "CUSTOM"


def test_data_cli_group_is_registered() -> None:
    result = CliRunner().invoke(app, ["data", "--help"])

    assert result.exit_code == 0
    assert "download" in result.output
    assert "build" in result.output


def test_data_handler_uses_shared_service_and_renders_correlation() -> None:
    from vnalpha.commands.handlers.data import handle_data
    from vnalpha.data_provisioning.service import (
        DataProvisioningResult,
        ProvisioningStatus,
    )

    service = MagicMock()
    service.execute.return_value = DataProvisioningResult(
        status=ProvisioningStatus.SUCCESS,
        operation="download",
        artifact="ohlcv",
        correlation_id="corr-77",
        counts={"inserted": 4, "skipped": 1},
        symbol="FPT",
        source="vndirect",
    )

    result = handle_data(
        parse("/data download ohlcv fpt --source vndirect"),
        conn=MagicMock(),
        service=service,
    )

    assert result.status == "SUCCESS"
    assert result.title == "/data download ohlcv"
    assert result.panels[0].content["correlation_id"] == "corr-77"
    request = service.execute.call_args.args[0]
    assert request.symbol == "fpt"
    assert request.source == "vndirect"


def test_data_cli_validates_before_opening_connection(monkeypatch) -> None:
    from vnalpha.cli_app import data as data_cli

    get_connection = MagicMock()
    migrations = MagicMock()
    monkeypatch.setattr("vnalpha.warehouse.connection.get_connection", get_connection)
    monkeypatch.setattr("vnalpha.warehouse.migrations.run_migrations", migrations)
    result = CliRunner().invoke(data_cli.app, ["build", "features", "FPT", "--date", "bad"])
    assert result.exit_code != 0
    get_connection.assert_not_called()
    migrations.assert_not_called()


def test_data_handler_rejects_unknown_options_before_service_execution() -> None:
    from vnalpha.commands.errors import CommandValidationError
    from vnalpha.commands.handlers.data import handle_data

    service = MagicMock()

    with pytest.raises(CommandValidationError, match="Unsupported option"):
        handle_data(
            parse("/data download ohlcv FPT --provider unapproved"),
            conn=MagicMock(),
            service=service,
        )

    service.execute.assert_not_called()


@pytest.mark.parametrize(
    ("raw", "operation", "artifact"),
    [
        ("/data download symbols", "download", "symbols"),
        ("/data download ohlcv FPT", "download", "ohlcv"),
        ("/data download index VNINDEX", "download", "index"),
        ("/data build canonical FPT", "build", "canonical"),
        ("/data build features FPT --date 2026-07-10", "build", "features"),
        ("/data build score FPT --date 2026-07-10", "build", "score"),
        ("/data build market-regime --date 2026-07-10", "build", "market-regime"),
        (
            "/data build sector-strength --date 2026-07-10",
            "build",
            "sector-strength",
        ),
    ],
)
def test_data_handler_routes_every_supported_form(
    raw: str, operation: str, artifact: str
) -> None:
    from vnalpha.commands.handlers.data import handle_data
    from vnalpha.data_provisioning.service import (
        DataProvisioningResult,
        ProvisioningStatus,
    )

    service = MagicMock()
    service.execute.return_value = DataProvisioningResult(
        status=ProvisioningStatus.SUCCESS,
        operation=operation,
        artifact=artifact,
        correlation_id="corr-77",
    )

    result = handle_data(parse(raw), conn=MagicMock(), service=service)

    assert result.status == "SUCCESS"
    request = service.execute.call_args.args[0]
    assert request.operation == operation
    assert request.artifact == artifact


@pytest.mark.parametrize(
    "module_name",
    [
        "vnalpha.cli_app.sync",
        "vnalpha.cli_app.build",
        "vnalpha.cli_app.score",
    ],
)
def test_legacy_cli_modules_delegate_to_shared_data_service(module_name: str) -> None:
    module = __import__(module_name, fromlist=["placeholder"])

    assert "DataProvisioningService" in inspect.getsource(module)
