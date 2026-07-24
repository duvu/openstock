from __future__ import annotations

import json
from datetime import date

import duckdb
import typer
from typer.testing import CliRunner

from vnalpha.cli_app import common as cli_common
from vnalpha.cli_app import maintain as maintain_cli
from vnalpha.core.config import (
    AppConfig,
    VnstockServiceConfig,
    WarehouseConfig,
    reset_config,
)
from vnalpha.data_provisioning.source_policy import SourcePolicyResolver
from vnalpha.maintenance import runtime_identity
from vnalpha.maintenance.models import (
    DailyMaintenanceResult,
    MaintenanceRunStatus,
    MaintenanceStageResult,
    MaintenanceStageStatus,
)
from vnalpha.maintenance.runtime_identity import (
    RuntimeBuildMatchStatus,
    collect_runtime_identity,
)
from vnalpha.maintenance.software_identity import SoftwareIdentity
from vnalpha.observability.context import reset_run_context


def test_daily_cli_persists_noop_invocation(tmp_path, monkeypatch) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    monkeypatch.setenv("VNALPHA_WAREHOUSE_PATH", str(warehouse))
    reset_config()
    monkeypatch.setattr(
        maintain_cli,
        "resolve_software_identity",
        lambda: SoftwareIdentity("1.2.3", "a" * 40, "clean"),
    )

    try:
        result = CliRunner().invoke(
            maintain_cli.app,
            ["daily", "--date", "2026-07-19", "--json"],
        )
        assert result.exit_code == 0, result.output

        conn = duckdb.connect(str(warehouse))
        row = conn.execute(
            "SELECT status, package_version, source_commit, tree_state FROM maintenance_run"
        ).fetchone()
        conn.close()
        assert row == ("NOOP", "1.2.3", "a" * 40, "clean")
    finally:
        reset_config()


def test_daily_cli_commits_partial_symbol_results_before_exit(
    tmp_path, monkeypatch
) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    monkeypatch.setenv("VNALPHA_WAREHOUSE_PATH", str(warehouse))
    reset_config()
    partial_result = DailyMaintenanceResult(
        status=MaintenanceRunStatus.PARTIAL,
        requested_date="2026-07-23",
        resolved_date="2026-07-23",
        correlation_id="partial-symbol-results",
        stages=(
            MaintenanceStageResult(
                "incremental_ohlcv",
                MaintenanceStageStatus.PARTIAL,
                counts={"inserted": 1},
            ),
        ),
        requested_symbols=("FPT", "MSN"),
        successful_symbols=("FPT",),
        failed_symbols=("MSN",),
        diagnostics_refs=(),
        mutated=True,
    )

    class PartialMaintenanceService:
        def __init__(self, conn, **_kwargs) -> None:
            self.conn = conn

        def run(self, _request) -> DailyMaintenanceResult:
            self.conn.execute("CREATE TABLE partial_run_probe (symbol VARCHAR)")
            self.conn.execute("INSERT INTO partial_run_probe VALUES ('FPT')")
            return partial_result

    monkeypatch.setattr(
        maintain_cli, "DailyMaintenanceService", PartialMaintenanceService
    )
    monkeypatch.setattr(
        maintain_cli,
        "resolve_software_identity",
        lambda: SoftwareIdentity("1.2.3", "a" * 40, "clean"),
    )

    try:
        result = CliRunner().invoke(
            maintain_cli.app,
            ["daily", "--date", "2026-07-23", "--symbols", "FPT,MSN", "--json"],
        )
        assert result.exit_code == 3, result.output

        conn = duckdb.connect(str(warehouse))
        persisted_run = conn.execute(
            "SELECT status, successful_symbol_count, failed_symbol_count "
            "FROM maintenance_run"
        ).fetchone()
        persisted_symbol = conn.execute(
            "SELECT symbol FROM partial_run_probe"
        ).fetchone()
        conn.close()
        assert persisted_run == ("PARTIAL", 1, 1)
        assert persisted_symbol == ("FPT",)
    finally:
        reset_config()


def test_cli_records_effective_runtime_identity_in_metadata_mode(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        runtime_identity,
        "_source_checkout_commit",
        lambda _path: "b" * 40,
    )
    identity = collect_runtime_identity(
        config=AppConfig(
            vnstock=VnstockServiceConfig(
                base_url=(
                    "http://svcuser:supersecret@vnstock.test:6900/v1?"
                    "signature=supersecret"
                )
            ),
            warehouse=WarehouseConfig(path=tmp_path / "warehouse.duckdb"),
        ),
        software_identity=SoftwareIdentity("1.2.3", "a" * 40, "clean"),
        source_policy_resolver=SourcePolicyResolver(
            configured_sources={"equity.ohlcv": "vci"}
        ),
        current_checkout_path=tmp_path,
    )
    assert identity.build_match_status is RuntimeBuildMatchStatus.STALE

    monkeypatch.setattr(cli_common, "collect_runtime_identity", lambda: identity)
    monkeypatch.setenv("VNALPHA_LOG_ROOT", str(tmp_path / "logs"))
    monkeypatch.setenv("VNALPHA_LOG_CONTENT_MODE", "metadata")
    app = typer.Typer()
    cli_common.configure_app(app)

    @app.command()
    def status() -> None:
        typer.echo("ready")

    reset_run_context()
    try:
        result = CliRunner().invoke(app, ["status"])
    finally:
        reset_run_context()

    assert result.exit_code == 0, result.output
    app_log = next((tmp_path / "logs" / "runs").glob("*/app.jsonl"))
    records = [json.loads(line) for line in app_log.read_text().splitlines()]
    fields = next(
        record for record in records if record["event_type"] == "RUNTIME_IDENTITY"
    )
    assert fields["application_version"] == "1.2.3"
    assert fields["source_commit"] == "a" * 40
    assert fields["current_source_commit"] == "b" * 40
    assert fields["build_match_status"] == "STALE"
    assert fields["warehouse_path"] == str(tmp_path / "warehouse.duckdb")
    assert "vnstock_service_url" not in fields
    assert fields["provider_source_policy"] == {
        "reference.symbols": {
            "source": None,
            "mode": "AUTO",
            "fallback_allowed": True,
        },
        "equity.ohlcv": {
            "source": "vci",
            "mode": "CONFIGURED",
            "fallback_allowed": True,
        },
        "index.ohlcv": {
            "source": None,
            "mode": "AUTO",
            "fallback_allowed": True,
        },
        "reference.index_membership_snapshot": {
            "source": "vci",
            "mode": "CONFIGURED",
            "fallback_allowed": False,
        },
        "reference.sector_membership_snapshot": {
            "source": "vci",
            "mode": "CONFIGURED",
            "fallback_allowed": False,
        },
    }
    assert fields["package_installation_path"].endswith("/vnalpha")
    assert fields["process_started_at"] is not None

    monkeypatch.setenv("VNALPHA_LOG_ROOT", str(tmp_path / "redacted-logs"))
    monkeypatch.setenv("VNALPHA_LOG_CONTENT_MODE", "redacted")
    reset_run_context()
    try:
        redacted_result = CliRunner().invoke(app, ["status"])
    finally:
        reset_run_context()

    assert redacted_result.exit_code == 0, redacted_result.output
    redacted_log = next((tmp_path / "redacted-logs" / "runs").glob("*/app.jsonl"))
    redacted_records = [
        json.loads(line) for line in redacted_log.read_text().splitlines()
    ]
    redacted_identity = next(
        record
        for record in redacted_records
        if record["event_type"] == "RUNTIME_IDENTITY"
    )
    assert redacted_identity["vnstock_service_url"] == "http://vnstock.test:6900"


def _maintenance_result(
    session_date: date, correlation_id: str
) -> DailyMaintenanceResult:
    return DailyMaintenanceResult(
        status=MaintenanceRunStatus.SUCCESS,
        requested_date=session_date.isoformat(),
        resolved_date=session_date.isoformat(),
        correlation_id=correlation_id,
        stages=(
            MaintenanceStageResult(
                "incremental_ohlcv",
                MaintenanceStageStatus.SUCCESS,
                counts={"inserted": 1},
            ),
        ),
        requested_symbols=("FPT",),
        successful_symbols=("FPT",),
        failed_symbols=(),
        diagnostics_refs=(),
        mutated=True,
    )
