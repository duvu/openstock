from __future__ import annotations

from pathlib import Path

from vnalpha.maintenance.finalization import maybe_submit_session_finalization
from vnalpha.maintenance.producer import (
    MaintenanceProducer,
    MaintenanceProducerRequest,
    MaintenanceRunState,
)
from vnalpha.provisioning_queue import ProvisioningQueue
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator


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
    first = producer.produce(MaintenanceProducerRequest(date="2026-07-21"))
    resumed = producer.produce(
        MaintenanceProducerRequest(
            date="2026-07-21",
            maintenance_run_id=first.maintenance_run_id,
        )
    )

    assert first.state is MaintenanceRunState.ACQUIRING
    assert first.universe_snapshot_id == "snapshot-1"
    assert first.symbols == ("FPT", "VCB")
    assert first.expected_count == 3
    assert first.submitted_count == 3
    assert first.benchmark_job_id is not None
    assert resumed.maintenance_run_id == first.maintenance_run_id
    assert resumed.submitted_count == 0
    assert resumed.joined_count == 0
    assert resumed.mapped_count == 3

    blocked = maybe_submit_session_finalization(
        first.maintenance_run_id,
        warehouse_path=warehouse_path,
        queue_path=queue_path,
    )
    assert blocked.state == "ACQUIRING"
    queue = ProvisioningQueue(queue_path)
    while (job := queue.claim("test-worker")) is not None:
        queue.complete(job.job_id, "test-worker", "done")
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
