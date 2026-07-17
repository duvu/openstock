from __future__ import annotations

import json
from pathlib import Path

import duckdb
from typer.testing import CliRunner

from vnalpha.cli import app
from vnalpha.core.config import reset_config
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.status import WarehouseStatusCode, inspect_warehouse


def _migrated_warehouse(path: Path) -> None:
    with duckdb.connect(str(path)) as connection:
        run_migrations(connection)


def test_compatible_warehouse_is_verified_without_mutation(tmp_path: Path) -> None:
    path = tmp_path / "warehouse.duckdb"
    _migrated_warehouse(path)
    before = (path.stat().st_size, path.stat().st_mtime_ns)

    result = inspect_warehouse(path)

    assert result.code is WarehouseStatusCode.READY
    assert result.ready
    assert result.missing_schema == ()
    assert (path.stat().st_size, path.stat().st_mtime_ns) == before


def test_missing_warehouse_is_typed(tmp_path: Path) -> None:
    result = inspect_warehouse(tmp_path / "missing.duckdb")

    assert result.code is WarehouseStatusCode.MISSING
    assert not result.ready


def test_corrupt_warehouse_is_typed(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.duckdb"
    path.write_bytes(b"not a duckdb database")

    result = inspect_warehouse(path)

    assert result.code is WarehouseStatusCode.UNREADABLE
    assert not result.ready


def test_schema_drift_is_typed(tmp_path: Path) -> None:
    path = tmp_path / "stale.duckdb"
    with duckdb.connect(str(path)) as connection:
        connection.execute("CREATE TABLE legacy_only (id INTEGER)")

    result = inspect_warehouse(path)

    assert result.code is WarehouseStatusCode.SCHEMA_DRIFT
    assert not result.ready
    assert result.missing_schema


def test_missing_primary_key_is_schema_drift(tmp_path: Path) -> None:
    path = tmp_path / "constraint-drift.duckdb"
    _migrated_warehouse(path)
    with duckdb.connect(str(path)) as connection:
        connection.execute("DROP TABLE reference_membership_member")
        connection.execute(
            "CREATE TABLE reference_membership_member ("
            "snapshot_id VARCHAR NOT NULL, member_symbol VARCHAR NOT NULL)"
        )

    result = inspect_warehouse(path)

    assert result.code is WarehouseStatusCode.SCHEMA_DRIFT
    assert any("PRIMARY KEY" in item for item in result.missing_schema)


def test_warehouse_status_cli_json_exits_nonzero_for_drift(tmp_path: Path) -> None:
    path = tmp_path / "stale.duckdb"
    with duckdb.connect(str(path)) as connection:
        connection.execute("CREATE TABLE legacy_only (id INTEGER)")

    result = CliRunner().invoke(
        app,
        ["warehouse", "status", "--path", str(path), "--json"],
    )

    payload = json.loads(result.stdout)
    assert result.exit_code == 1
    assert payload["code"] == "schema_drift"
    assert payload["path"] == str(path)


def test_init_does_not_claim_ready_when_legacy_schema_remains_incompatible(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "legacy.duckdb"
    with duckdb.connect(str(path)) as connection:
        connection.execute(
            "CREATE TABLE research_scenario_plan ("
            "scenario_plan_id VARCHAR PRIMARY KEY, symbol VARCHAR NOT NULL, "
            "date DATE NOT NULL, generated_at TIMESTAMPTZ NOT NULL, "
            "plan_json VARCHAR NOT NULL, setup_analysis_date DATE, "
            "level_snapshot_date DATE, evidence_snapshot_json VARCHAR NOT NULL, "
            "correlation_id VARCHAR NOT NULL, UNIQUE(symbol, date))"
        )
    monkeypatch.setenv("VNALPHA_WAREHOUSE_PATH", str(path))
    reset_config()

    result = CliRunner().invoke(app, ["init"])

    reset_config()
    assert result.exit_code == 1
    assert "Warehouse ready." not in result.stdout
    assert "schema_drift" in result.stdout
    assert str(path) in result.stdout
