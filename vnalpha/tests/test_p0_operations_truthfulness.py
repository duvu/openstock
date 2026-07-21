from __future__ import annotations

from datetime import date

import duckdb
from typer.testing import CliRunner

from vnalpha.cli_app import maintain as maintain_cli
from vnalpha.maintenance.models import (
    DailyMaintenanceResult,
    MaintenanceRunStatus,
    MaintenanceStageResult,
    MaintenanceStageStatus,
)
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
