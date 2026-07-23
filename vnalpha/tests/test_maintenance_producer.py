from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb

from vnalpha.ingestion.trading_calendar import SessionRange, VietnamSessionCalendar
from vnalpha.maintenance.finalization import (
    maybe_submit_session_finalization,
    recover_session_finalization,
)
from vnalpha.maintenance.producer import (
    MaintenanceProducer,
    MaintenanceProducerRequest,
    MaintenanceRunState,
)
from vnalpha.provisioning_queue import ProvisioningJobStatus, ProvisioningQueue
from vnalpha.provisioning_queue.worker import ProvisioningWorker
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
    unsupported_worker = ProvisioningWorker(
        queue,
        worker_id="test-acquisition-terminal",
        warehouse_path=warehouse_path,
        handlers=(),
    )
    for _ in range(3):
        terminal = unsupported_worker.process_one()
        assert terminal is not None
        assert terminal.status is ProvisioningJobStatus.FAILED
    assert len(queue.list()) == 4

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
    assert finalized.joined
    assert finalized.job_id is not None
    assert duplicate.joined
    assert duplicate.job_id == finalized.job_id
    recovered = recover_session_finalization(
        maintenance_run_id=first.maintenance_run_id,
        warehouse_path=warehouse_path,
        queue_path=queue_path,
    )
    assert len(recovered) == 1
    assert recovered[0].joined
    assert recovered[0].job_id == finalized.job_id

    failed_finalization = ProvisioningWorker(
        queue,
        worker_id="test-finalizer",
        warehouse_path=warehouse_path,
    ).process_one()
    assert failed_finalization is not None
    assert failed_finalization.status is ProvisioningJobStatus.FAILED
    with WarehouseWriteCoordinator(path=warehouse_path).transaction() as connection:
        run_status, stage_status = connection.execute(
            "SELECT r.status, s.status FROM maintenance_run r "
            "JOIN maintenance_finalization_stage s ON s.run_id = r.run_id "
            "WHERE r.run_id = ? AND s.stage_name = 'finalization-coverage'",
            [first.maintenance_run_id],
        ).fetchone()
    assert run_status == "FAILED"
    assert stage_status == "FAILED"

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
    completed_finalization = ProvisioningWorker(
        queue,
        worker_id="test-ready-finalizer",
        warehouse_path=warehouse_path,
    ).process_one()
    assert completed_finalization is not None
    assert completed_finalization.status is ProvisioningJobStatus.SUCCEEDED
    completed_goal = queue.get(ready_finalization.job_id)
    assert completed_goal is not None
    replay = queue.submit_or_join(completed_goal.goal, priority=0)
    assert not replay.joined_existing_job
    replayed_finalization = ProvisioningWorker(
        queue,
        worker_id="test-ready-finalizer-replay",
        warehouse_path=warehouse_path,
    ).process_one()
    assert replayed_finalization is not None
    assert replayed_finalization.status is ProvisioningJobStatus.SUCCEEDED
    with WarehouseWriteCoordinator(path=warehouse_path).transaction() as connection:
        finalization_stage_count = connection.execute(
            "SELECT COUNT(*) FROM maintenance_finalization_stage WHERE run_id = ?",
            [ready.maintenance_run_id],
        ).fetchone()[0]
    assert finalization_stage_count == 7

    with WarehouseWriteCoordinator(path=warehouse_path).transaction() as connection:
        connection.execute(
            "INSERT INTO reference_membership_snapshot "
            "(snapshot_id, ingestion_run_id, dataset, membership_type, entity_id, "
            "observed_at, provider, source_query, member_count, status, "
            "snapshot_semantics, lineage_json, correlation_id) "
            "VALUES ('snapshot-partial', 'run-partial', 'reference.membership', "
            "'universe', 'VN30', CURRENT_TIMESTAMP, 'test', 'fixture', 5, "
            "'SUCCESS', 'frozen', '{}', 'corr-partial')"
        )
        connection.executemany(
            "INSERT INTO reference_membership_member (snapshot_id, member_symbol) "
            "VALUES ('snapshot-partial', ?)",
            [("FPT",), ("VCB",), ("HPG",), ("MWG",), ("VNM",)],
        )
        connection.executemany(
            "INSERT INTO symbol_master (symbol) VALUES (?)",
            [("HPG",), ("MWG",), ("VNM",)],
        )
        for symbol in ("HPG", "MWG"):
            _seed_ready_canonical(
                connection,
                symbol=symbol,
                end_date="2026-07-21",
            )

    partial = producer.produce(
        MaintenanceProducerRequest(
            date="2026-07-21",
            snapshot_id="snapshot-partial",
        )
    )
    assert partial.expected_count == 1
    terminal_acquisition = ProvisioningWorker(
        queue,
        worker_id="test-partial-acquisition",
        warehouse_path=warehouse_path,
        handlers=(),
    ).process_one()
    assert terminal_acquisition is not None
    assert terminal_acquisition.status is ProvisioningJobStatus.FAILED
    partial_finalization = ProvisioningWorker(
        queue,
        worker_id="test-partial-finalizer",
        warehouse_path=warehouse_path,
    ).process_one()
    assert partial_finalization is not None
    assert partial_finalization.status is ProvisioningJobStatus.SUCCEEDED
    with WarehouseWriteCoordinator(path=warehouse_path).transaction() as connection:
        partial_status = connection.execute(
            "SELECT status FROM maintenance_run WHERE run_id = ?",
            [partial.maintenance_run_id],
        ).fetchone()[0]
    assert partial_status == "PARTIAL"
