from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
import typer
from typer.testing import CliRunner


def test_market_regime_builder_receives_date_and_complete_is_success() -> None:
    from vnalpha.data_provisioning.service import (
        DataProvisioningDependencies,
        DataProvisioningRequest,
        DataProvisioningService,
        ProvisioningStatus,
    )

    snapshot = MagicMock(
        quality="COMPLETE",
        methodology_version="market-regime-v1",
        generated_at="2026-07-10T10:00:00+00:00",
        lineage={"benchmark_input": "canonical_ohlcv"},
    )
    builder = MagicMock(return_value=snapshot)
    service = DataProvisioningService(
        MagicMock(),
        dependencies=DataProvisioningDependencies(build_market_regime=builder),
    )

    result = service.execute(
        DataProvisioningRequest("build", "market-regime", date="2026-07-10")
    )

    assert builder.call_args.args[1] == date(2026, 7, 10)
    assert result.status is ProvisioningStatus.SUCCESS
    assert result.freshness == "exact"
    assert result.lineage["methodology_version"] == "market-regime-v1"


def test_sector_builder_receives_date_and_ok_is_success() -> None:
    from vnalpha.data_provisioning.service import (
        DataProvisioningDependencies,
        DataProvisioningRequest,
        DataProvisioningService,
        ProvisioningStatus,
    )

    build_result = MagicMock(
        quality="OK",
        snapshots=(object(), object()),
        lineage={"methodology_version": "sector-strength-v1"},
    )
    builder = MagicMock(return_value=build_result)
    service = DataProvisioningService(
        MagicMock(),
        dependencies=DataProvisioningDependencies(build_sector_strength=builder),
    )

    result = service.execute(
        DataProvisioningRequest("build", "sector-strength", date="2026-07-10")
    )

    assert builder.call_args.args[1] == date(2026, 7, 10)
    assert result.status is ProvisioningStatus.SUCCESS
    assert result.counts == {"sectors": 2}


@pytest.mark.parametrize(
    ("artifact", "dependency_name", "adapter_result", "problem_key"),
    [
        ("symbols", "sync_symbols", {"synced": 3, "errors": 1}, "errors"),
        (
            "canonical",
            "build_canonical",
            {"upserted": 10, "rejected": 1},
            "rejected",
        ),
        (
            "features",
            "build_features",
            {"built": 3, "skipped": 1},
            "skipped",
        ),
    ],
)
def test_adapter_problem_counts_produce_partial_status(
    artifact: str,
    dependency_name: str,
    adapter_result: dict[str, int],
    problem_key: str,
) -> None:
    from vnalpha.data_provisioning.service import (
        DataProvisioningDependencies,
        DataProvisioningRequest,
        DataProvisioningService,
        ProvisioningStatus,
    )

    dependencies = DataProvisioningDependencies(
        **{dependency_name: MagicMock(return_value=adapter_result)}
    )
    service = DataProvisioningService(MagicMock(), dependencies=dependencies)
    if artifact == "symbols":
        request = DataProvisioningRequest("download", artifact)
    elif artifact == "canonical":
        request = DataProvisioningRequest("build", artifact, symbol="FPT")
    else:
        request = DataProvisioningRequest(
            "build", artifact, symbol="FPT", date="2026-07-10"
        )

    result = service.execute(request)

    assert result.status is ProvisioningStatus.PARTIAL
    assert result.counts[problem_key] == 1
    assert result.warnings


def test_runtime_adapter_failure_returns_sanitized_failed_result() -> None:
    from vnalpha.data_provisioning.service import (
        DataProvisioningDependencies,
        DataProvisioningRequest,
        DataProvisioningService,
        ProvisioningStatus,
    )

    adapter = MagicMock(side_effect=RuntimeError("provider unavailable"))
    service = DataProvisioningService(
        MagicMock(),
        dependencies=DataProvisioningDependencies(sync_ohlcv=adapter),
    )

    result = service.execute(DataProvisioningRequest("download", "ohlcv", symbol="FPT"))

    assert result.status is ProvisioningStatus.FAILED
    assert result.error == (
        "Data provisioning did not complete. Review the correlated audit record."
    )


@pytest.mark.parametrize(
    ("module_name", "request_case"),
    [
        (
            "vnalpha.cli_app.sync",
            ("download", "ohlcv", {"symbol": "FPT", "start": "bad"}),
        ),
        (
            "vnalpha.cli_app.build",
            ("build", "features", {"symbol": "FPT", "date": "bad"}),
        ),
        (
            "vnalpha.cli_app.score",
            ("build", "score", {"symbol": "FPT", "date": "bad"}),
        ),
    ],
)
def test_legacy_helpers_convert_validation_errors_to_clean_exit(
    module_name: str,
    request_case: tuple[str, str, dict[str, object]],
) -> None:
    from vnalpha.data_provisioning.service import DataProvisioningRequest

    module = __import__(module_name, fromlist=["placeholder"])
    operation, artifact, kwargs = request_case

    with pytest.raises(typer.Exit):
        module._execute(
            MagicMock(),
            DataProvisioningRequest(operation, artifact, **kwargs),
        )


def test_legacy_sync_without_selection_preserves_all_active_semantics(
    monkeypatch,
) -> None:
    from vnalpha.cli_app import sync as sync_cli
    from vnalpha.data_provisioning.service import (
        DataProvisioningResult,
        ProvisioningStatus,
    )

    captured = {}

    class Service:
        def __init__(self, _conn):
            pass

        def execute(self, request):
            captured["request"] = request
            return DataProvisioningResult(
                status=ProvisioningStatus.SUCCESS,
                operation="download",
                artifact="ohlcv",
                correlation_id="sync-all",
                counts={"inserted": 0, "skipped": 0},
            )

    monkeypatch.setattr(sync_cli, "DataProvisioningService", Service)
    monkeypatch.setattr("vnalpha.warehouse.connection.get_connection", MagicMock())
    monkeypatch.setattr("vnalpha.warehouse.migrations.run_migrations", MagicMock())

    result = CliRunner().invoke(sync_cli.app, ["ohlcv"])

    assert result.exit_code == 0
    assert captured["request"].symbols is None
    assert captured["request"].allow_all_symbols is True
