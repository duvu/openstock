from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import duckdb

from vnalpha.data_availability.artifact_readiness_models import ReadinessCapability
from vnalpha.data_availability.policy import DataAvailabilityPolicy
from vnalpha.data_provisioning.current_symbol_application import (
    CurrentSymbolProvisioningState,
    CurrentSymbolResearchApplication,
    CurrentSymbolResearchRequest,
    CurrentSymbolResearchStatus,
    CurrentSymbolWaitMode,
)
from vnalpha.provisioning_queue import ProvisioningQueue
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator


def test_ready_current_symbol_reuses_persisted_evidence_without_a_queue_job(
    tmp_path: Path,
) -> None:
    warehouse_path = tmp_path / "warehouse.duckdb"
    target_date = date(2024, 9, 30)
    with WarehouseWriteCoordinator(path=warehouse_path).transaction() as connection:
        run_migrations(conn=connection, emit_observability=False)
        connection.execute("INSERT INTO symbol_master (symbol) VALUES ('FPT')")
        connection.executemany(
            "INSERT INTO canonical_ohlcv "
            "(symbol, time, interval, close, selected_provider, quality_status) "
            "VALUES ('FPT', ?, '1D', 10.0, 'test', 'pass')",
            [
                ((target_date - timedelta(days=offset)).isoformat(),)
                for offset in range(5)
            ],
        )
    with duckdb.connect(str(warehouse_path), read_only=True) as connection:
        before = connection.execute("SELECT COUNT(*) FROM canonical_ohlcv").fetchone()[
            0
        ]

    result = CurrentSymbolResearchApplication(
        warehouse_path=warehouse_path,
        queue_path=tmp_path / "provisioning.sqlite3",
        policy=DataAvailabilityPolicy(min_required_bars=1),
    ).execute(
        CurrentSymbolResearchRequest(
            symbol="FPT",
            effective_date=target_date.isoformat(),
            requested_capability=ReadinessCapability.PRICE_ANALYSIS,
        )
    )

    with duckdb.connect(str(warehouse_path), read_only=True) as connection:
        after = connection.execute("SELECT COUNT(*) FROM canonical_ohlcv").fetchone()[0]
    assert result.status is CurrentSymbolResearchStatus.READY
    assert result.job_id is None
    assert result.provisioning is CurrentSymbolProvisioningState.REUSED
    assert result.correlation_id
    assert before == after
    assert not (tmp_path / "provisioning.sqlite3").exists()


def test_missing_current_symbol_work_joins_one_escalated_queue_job(
    tmp_path: Path,
) -> None:
    missing_warehouse_path = tmp_path / "missing-warehouse.duckdb"
    queue_path = tmp_path / "missing-provisioning.sqlite3"
    with WarehouseWriteCoordinator(
        path=missing_warehouse_path
    ).transaction() as connection:
        run_migrations(conn=connection, emit_observability=False)
        connection.execute("INSERT INTO symbol_master (symbol) VALUES ('FPT')")
    application = CurrentSymbolResearchApplication(
        warehouse_path=missing_warehouse_path,
        queue_path=queue_path,
        policy=DataAvailabilityPolicy(min_required_bars=1),
    )
    request = CurrentSymbolResearchRequest(
        symbol="FPT",
        effective_date="2024-09-30",
        requested_capability=ReadinessCapability.PRICE_ANALYSIS,
    )

    accepted = application.execute(request)
    pending = application.execute(
        replace(
            request,
            priority=3,
            wait_mode=CurrentSymbolWaitMode.WAIT_UP_TO,
            wait_timeout_seconds=0,
        )
    )

    job = ProvisioningQueue(queue_path).get(accepted.job_id)
    assert accepted.status is CurrentSymbolResearchStatus.ACCEPTED
    assert pending.status is CurrentSymbolResearchStatus.PENDING
    assert accepted.job_id == pending.job_id
    assert job is not None
    assert job.priority == 3
