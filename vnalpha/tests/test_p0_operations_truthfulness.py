from __future__ import annotations

from datetime import date

import duckdb
from typer.testing import CliRunner

from vnalpha.cli_app import maintain as maintain_cli
from vnalpha.core.config import AppConfig, VnstockServiceConfig, WarehouseConfig
from vnalpha.data_provisioning.source_policy import SourcePolicyResolver
from vnalpha.maintenance.models import (
    DailyMaintenanceResult,
    MaintenanceRunStatus,
    MaintenanceStageResult,
    MaintenanceStageStatus,
)
from vnalpha.maintenance.runtime_identity import collect_runtime_identity
from vnalpha.maintenance.software_identity import SoftwareIdentity


def test_daily_cli_persists_noop_invocation(tmp_path, monkeypatch) -> None:
    warehouse = tmp_path / "warehouse.duckdb"

    def _connection(*, ephemeral: bool):
        return duckdb.connect(":memory:" if ephemeral else str(warehouse))

    monkeypatch.setattr(maintain_cli, "_maintenance_connection", _connection)
    monkeypatch.setattr(
        maintain_cli,
        "resolve_software_identity",
        lambda: SoftwareIdentity("1.2.3", "a" * 40, "clean"),
    )

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


def test_runtime_identity_records_effective_runtime_configuration(tmp_path) -> None:
    identity = collect_runtime_identity(
        config=AppConfig(
            vnstock=VnstockServiceConfig(base_url="http://vnstock.test:6900"),
            warehouse=WarehouseConfig(path=tmp_path / "warehouse.duckdb"),
        ),
        software_identity=SoftwareIdentity("1.2.3", "a" * 40, "clean"),
        source_policy_resolver=SourcePolicyResolver(
            configured_sources={"equity.ohlcv": "vci"}
        ),
    )

    fields = identity.to_log_fields()

    assert fields["application_version"] == "1.2.3"
    assert fields["source_commit"] == "a" * 40
    assert fields["warehouse_path"] == str(tmp_path / "warehouse.duckdb")
    assert fields["vnstock_service_url"] == "http://vnstock.test:6900"
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
