from __future__ import annotations

import json
from datetime import date

import duckdb
import pytest
from typer.testing import CliRunner

from vnalpha.cli_app import maintain as maintain_cli
from vnalpha.cli_app.app import app as cli_app
from vnalpha.data_provisioning.service import (
    DataProvisioningResult,
    ProvisioningStatus,
)
from vnalpha.ingestion.models import (
    IngestionErrorCategory,
    SymbolIngestionResult,
    SymbolIngestionStatus,
)
from vnalpha.ingestion.trading_calendar import VietnamSessionCalendar
from vnalpha.maintenance.daily import (
    DailyMaintenanceRequest,
    DailyMaintenanceService,
    MaintenanceRunStatus,
    MaintenanceStageStatus,
)
from vnalpha.maintenance.models import (
    DailyMaintenanceResult,
    MaintenanceStageResult,
)
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _result(request, *, status=ProvisioningStatus.SUCCESS, counts=None, symbols=()):
    return DataProvisioningResult(
        status=status,
        operation=request.operation,
        artifact=request.artifact,
        correlation_id="corr-239",
        counts=counts or {},
        resolved_date=request.date,
        symbol=request.symbol,
        symbol_results=symbols,
    )


def test_daily_maintenance_preserves_good_symbols_after_empty_and_provider_failure(
    conn,
) -> None:
    # Given: one bounded symbol succeeds while another carries typed diagnostics.
    requests = []

    class FakeProvisioningService:
        def __init__(self, _conn) -> None:
            pass

        def execute(self, request):
            requests.append(request)
            if (request.operation, request.artifact) == ("sync", "daily"):
                return _result(
                    request,
                    status=ProvisioningStatus.PARTIAL,
                    symbols=(
                        SymbolIngestionResult(
                            "FPT", SymbolIngestionStatus.SUCCESS, None, None, "KBS"
                        ),
                        SymbolIngestionResult(
                            "VNM",
                            SymbolIngestionStatus.FAILED,
                            None,
                            None,
                            "VCI",
                            error_category=IngestionErrorCategory.HTTP,
                            retryable=True,
                            diagnostics_ref="req-239-vnm",
                            diagnostics={
                                "http_status": 503,
                                "service_error_code": "no_healthy_provider",
                            },
                        ),
                        SymbolIngestionResult(
                            "HPG",
                            SymbolIngestionStatus.EMPTY,
                            0,
                            "Provider returned no rows.",
                            "KBS",
                            retryable=False,
                            diagnostics_ref="req-239-hpg-empty",
                        ),
                    ),
                )
            if (request.operation, request.artifact) == ("gaps", "ohlcv"):
                return _result(request, counts={"true_gaps": 0})
            if (request.operation, request.artifact) == ("build", "canonical"):
                return _result(request, counts={"upserted": 3, "rejected": 0})
            return _result(request, counts={"built": 1})

    # When: the deterministic daily chain runs for both symbols.
    result = DailyMaintenanceService(
        conn, provisioning_factory=FakeProvisioningService
    ).run(
        DailyMaintenanceRequest(
            date="2026-07-17",
            symbols=("FPT", "VNM", "HPG"),
        )
    )

    # Then: the good symbol reaches downstream stages and the failed one does not.
    assert result.status is MaintenanceRunStatus.PARTIAL
    assert result.successful_symbols == ("FPT",)
    assert result.failed_symbols == ("HPG", "VNM")
    assert result.diagnostics_refs == ("req-239-vnm", "req-239-hpg-empty")
    canonical_symbols = [
        request.symbol
        for request in requests
        if (request.operation, request.artifact) == ("build", "canonical")
    ]
    assert canonical_symbols == ["VNINDEX", "FPT"]
    feature_request = next(
        request
        for request in requests
        if (request.operation, request.artifact) == ("build", "features")
    )
    assert feature_request.symbols == ("FPT",)


def test_daily_maintenance_dry_run_is_mutation_free(conn) -> None:
    # Given: a service that would fail the test if a mutating adapter executes.
    class ForbiddenProvisioningService:
        def __init__(self, _conn) -> None:
            pass

        def execute(self, request):
            raise AssertionError(f"dry-run executed {request.operation}")

    before = conn.execute("SELECT COUNT(*) FROM ingestion_run").fetchone()

    # When: the same daily request is previewed.
    result = DailyMaintenanceService(
        conn, provisioning_factory=ForbiddenProvisioningService
    ).run(
        DailyMaintenanceRequest(
            date="2026-07-17",
            symbols=("FPT",),
            dry_run=True,
        )
    )

    # Then: all work is planned and the warehouse remains byte-semantically unchanged.
    assert result.status is MaintenanceRunStatus.SUCCESS
    assert result.mutated is False
    assert all(
        stage.status is MaintenanceStageStatus.PLANNED for stage in result.stages
    )
    assert conn.execute("SELECT COUNT(*) FROM ingestion_run").fetchone() == before


def test_daily_maintenance_non_trading_day_is_clean_noop(conn) -> None:
    calls = []

    class ForbiddenProvisioningService:
        def __init__(self, _conn) -> None:
            pass

        def execute(self, request):
            calls.append(request)
            raise AssertionError("non-trading day must not provision")

    result = DailyMaintenanceService(
        conn, provisioning_factory=ForbiddenProvisioningService
    ).run(DailyMaintenanceRequest(date="2026-07-19"))

    assert result.status is MaintenanceRunStatus.NOOP
    assert result.mutated is False
    assert calls == []


def test_default_calendar_excludes_published_2026_exchange_holidays() -> None:
    calendar = VietnamSessionCalendar()

    assert calendar.version == "hnx-vnx-2026-1403-1517"
    for holiday in (
        "2026-01-01",
        "2026-01-02",
        "2026-02-16",
        "2026-02-20",
        "2026-04-27",
        "2026-04-30",
        "2026-05-01",
        "2026-08-31",
        "2026-09-02",
    ):
        assert calendar.is_session(date.fromisoformat(holiday)) is False
    assert calendar.is_session(date(2026, 2, 23)) is True


def test_daily_maintenance_empty_warehouse_fails_truthfully(conn) -> None:
    requests = []

    class EmptyProvisioningService:
        def __init__(self, _conn) -> None:
            pass

        def execute(self, request):
            requests.append(request)
            return _result(request)

    result = DailyMaintenanceService(
        conn, provisioning_factory=EmptyProvisioningService
    ).run(DailyMaintenanceRequest(date="2026-07-17"))

    assert result.status is MaintenanceRunStatus.FAILED
    assert result.successful_symbols == ()
    assert result.failed_symbols == ()
    assert requests[0].operation == "download"
    assert requests[0].artifact == "symbols"
    assert result.stages[-1].name == "incremental_ohlcv"
    assert result.stages[-1].status is MaintenanceStageStatus.FAILED


def test_daily_maintenance_runs_bounded_gap_repair_before_canonical(conn) -> None:
    requests = []

    class GapProvisioningService:
        def __init__(self, _conn) -> None:
            pass

        def execute(self, request):
            requests.append((request.operation, request.artifact, request.symbol))
            if (request.operation, request.artifact) == ("gaps", "ohlcv"):
                return _result(request, counts={"true_gaps": 1})
            return _result(request, counts={"built": 1})

    DailyMaintenanceService(conn, provisioning_factory=GapProvisioningService).run(
        DailyMaintenanceRequest(date="2026-07-17", symbols=("FPT",))
    )

    repair_index = requests.index(("repair", "ohlcv", "FPT"))
    canonical_index = requests.index(("build", "canonical", "FPT"))
    assert repair_index < canonical_index


def test_current_warehouse_rerun_skips_acquisition_and_preserves_row_counts(
    conn,
) -> None:
    conn.execute(
        "INSERT INTO symbol_source_snapshot "
        "(snapshot_id, ingestion_run_id, source, is_authoritative, snapshot_status, "
        "completed_at) VALUES ('snapshot-current', 'run-current', 'KBS', false, "
        "'SUCCESS', '2026-07-17T08:00:00+07:00')"
    )
    conn.execute(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, close, quality_status) VALUES "
        "('FPT', '2026-07-17', '1D', 100.0, 'pass'), "
        "('VNINDEX', '2026-07-17', '1D', 1300.0, 'pass')"
    )
    requests = []

    class CurrentProvisioningService:
        def __init__(self, _conn) -> None:
            pass

        def execute(self, request):
            requests.append((request.operation, request.artifact, request.symbol))
            return _result(request, counts={"built": 1})

    service = DailyMaintenanceService(
        conn, provisioning_factory=CurrentProvisioningService
    )
    first = service.run(DailyMaintenanceRequest(date="2026-07-17", symbols=("FPT",)))
    table_names = (
        "canonical_ohlcv",
        "feature_snapshot",
        "candidate_score",
        "group_context_snapshot",
        "memory_event",
        "memory_claim",
        "memory_document",
        "memory_compaction_run",
    )
    after_first = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in table_names
    }
    second = service.run(DailyMaintenanceRequest(date="2026-07-17", symbols=("FPT",)))
    after_second = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in table_names
    }

    assert not any(operation in {"download", "sync"} for operation, _, _ in requests)
    assert first.status == second.status
    assert after_second == after_first


def test_maintain_cli_json_preserves_partial_exit_code(monkeypatch) -> None:
    partial = DailyMaintenanceResult(
        status=MaintenanceRunStatus.PARTIAL,
        requested_date="2026-07-17",
        resolved_date="2026-07-17",
        correlation_id="corr-cli-239",
        stages=(
            MaintenanceStageResult("incremental_ohlcv", MaintenanceStageStatus.PARTIAL),
        ),
        requested_symbols=("FPT", "VNM"),
        successful_symbols=("FPT",),
        failed_symbols=("VNM",),
        diagnostics_refs=("diag-vnm",),
        mutated=True,
    )

    class PartialMaintenanceService:
        def __init__(self, _conn, *, provisioning_factory=None) -> None:
            pass

        def run(self, _request):
            return partial

    monkeypatch.setattr(
        maintain_cli, "DailyMaintenanceService", PartialMaintenanceService
    )
    monkeypatch.setattr(
        maintain_cli,
        "_maintenance_connection",
        lambda *, ephemeral: duckdb.connect(":memory:"),
    )

    result = CliRunner().invoke(
        cli_app,
        ["maintain", "daily", "--date", "2026-07-17", "--json"],
    )
    payload = json.loads(result.stdout)

    assert result.exit_code == 3
    assert payload["schema_version"] == 1
    assert payload["status"] == "PARTIAL"
    assert payload["effective_session"] == "2026-07-17"
    assert payload["diagnostics_refs"] == ["diag-vnm"]
