from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb

from vnalpha.ingestion.trading_calendar import SessionRange, VietnamSessionCalendar
from vnalpha.maintenance.finalization import maybe_submit_session_finalization
from vnalpha.maintenance.producer import (
    MaintenanceProducer,
    MaintenanceProducerRequest,
    MaintenanceRunState,
)
from vnalpha.provisioning_queue import ProvisioningQueue
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator


def _seed_ready_canonical(
    connection: duckdb.DuckDBPyConnection,
    *,
    symbol: str,
    end_date: str,
) -> None:
    calendar = VietnamSessionCalendar()
    end = date.fromisoformat(end_date)
    start = calendar.rewind_sessions(end, 120)
    sessions = [
        session.isoformat()
        for session in calendar.sessions(SessionRange(start=start, end=end))
    ]
    connection.executemany(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, close, selected_provider, quality_status) "
        "VALUES (?, ?, '1D', 10.0, 'VCI', 'pass')",
        [(symbol, session) for session in sessions],
    )


def test_maintenance_producer_freezes_goals_and_resumes_idempotently(
    tmp_path: Path,
) -> None:
    warehouse_path = tmp_path / "warehouse.duckdb"
    queue_path = tmp_path / "queue.sqlite3"
    with WarehouseWriteCoordinator(path=warehouse_path).transaction() as connection:
        run_migrations(conn=connection, emit_observability=False)
        connection.execute(
            "INSERT INTO reference_membership_snapshot "
            "(snapshot_id, ingestion_run_id, dataset, membership_type, entity_id, "
            "observed_at, provider, source_query, member_count, status, "
            "snapshot_semantics, lineage_json, correlation_id) "
            "VALUES ('snapshot-1', 'run-1', 'reference.membership', 'universe', "
            "'VN30', CURRENT_TIMESTAMP, 'test', 'fixture', 2, 'SUCCESS', "
            "'frozen', '{}', 'corr-1')"
        )
        connection.executemany(
            "INSERT INTO reference_membership_member (snapshot_id, member_symbol) "
            "VALUES ('snapshot-1', ?)",
            [("FPT",), ("VCB",)],
        )

    producer = MaintenanceProducer(
        warehouse_path=warehouse_path,
        queue_path=queue_path,
    )
    first = producer.produce(
        MaintenanceProducerRequest(date="2026-07-21", snapshot_id="snapshot-1")
    )

    assert first.state is MaintenanceRunState.ACQUIRING
    assert first.universe_snapshot_id == "snapshot-1"
    assert first.symbols == ("FPT", "VCB")
    assert first.expected_count == 3
    assert first.submitted_count == 3
    assert first.benchmark_job_id is not None

    queue = ProvisioningQueue(queue_path)
    with WarehouseWriteCoordinator(path=warehouse_path).transaction() as connection:
        connection.execute(
            "UPDATE maintenance_run_job SET job_id = NULL, mapped_at = NULL WHERE maintenance_run_id = ? AND entity_id = 'FPT'",
            [first.maintenance_run_id],
        )
    blocked = maybe_submit_session_finalization(
        first.maintenance_run_id,
        warehouse_path=warehouse_path,
        queue_path=queue_path,
    )
    assert blocked.state == "ACQUIRING"
    while (job := queue.claim("test-worker")) is not None:
        queue.complete(job.job_id, "test-worker", "done")

    resumed = producer.produce(
        MaintenanceProducerRequest(
            date="2026-07-22",
            universe="VN100",
            snapshot_id="other-snapshot",
            maintenance_run_id=first.maintenance_run_id,
            source_policy_version="policy-v2",
        )
    )
    assert resumed.maintenance_run_id == first.maintenance_run_id
    assert resumed.resolved_session == first.resolved_session
    assert resumed.universe_snapshot_id == first.universe_snapshot_id
    assert resumed.symbols == first.symbols
    assert resumed.source_policy_version == first.source_policy_version
    assert resumed.correlation_id == first.correlation_id
    assert resumed.submitted_count == 0
    assert resumed.joined_count == 0
    assert resumed.mapped_count == 3
    assert len(queue.list()) == 3

    finalized = maybe_submit_session_finalization(
        first.maintenance_run_id,
        warehouse_path=warehouse_path,
        queue_path=queue_path,
    )
    duplicate = maybe_submit_session_finalization(
        first.maintenance_run_id,
        warehouse_path=warehouse_path,
        queue_path=queue_path,
    )
    assert finalized.state == "FINALIZATION_QUEUED"
    assert finalized.submitted
    assert finalized.job_id is not None
    assert duplicate.joined
    assert duplicate.job_id == finalized.job_id

    with WarehouseWriteCoordinator(path=warehouse_path).transaction() as connection:
        connection.execute(
            "INSERT INTO reference_membership_snapshot "
            "(snapshot_id, ingestion_run_id, dataset, membership_type, entity_id, "
            "observed_at, provider, source_query, member_count, status, "
            "snapshot_semantics, lineage_json, correlation_id) "
            "VALUES ('snapshot-ready', 'run-ready', 'reference.membership', "
            "'universe', 'VN30', CURRENT_TIMESTAMP, 'test', 'fixture', 2, "
            "'SUCCESS', 'frozen', '{}', 'corr-ready')"
        )
        connection.executemany(
            "INSERT INTO reference_membership_member (snapshot_id, member_symbol) "
            "VALUES ('snapshot-ready', ?)",
            [("FPT",), ("VCB",)],
        )
        connection.executemany(
            "INSERT INTO symbol_master (symbol) VALUES (?)",
            [("FPT",), ("VCB",)],
        )
        for symbol in ("FPT", "VCB", "VNINDEX"):
            _seed_ready_canonical(
                connection,
                symbol=symbol,
                end_date="2026-07-21",
            )

    ready = producer.produce(
        MaintenanceProducerRequest(
            date="2026-07-21",
            snapshot_id="snapshot-ready",
        )
    )
    assert ready.state is MaintenanceRunState.ACQUIRING
    assert ready.expected_count == 0
    assert ready.submitted_count == 0
    assert ready.joined_count == 0
    assert ready.mapped_count == 0
    assert ready.benchmark_job_id is None
    assert ready.symbol_job_ids == ()
    assert len(queue.list()) == 4
    ready_finalization = maybe_submit_session_finalization(
        ready.maintenance_run_id,
        warehouse_path=warehouse_path,
        queue_path=queue_path,
    )
    assert ready_finalization.state == "FINALIZATION_QUEUED"
    assert ready_finalization.submitted
    assert len(queue.list()) == 5
