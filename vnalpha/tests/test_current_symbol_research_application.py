from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import duckdb
from typer.testing import CliRunner

from vnalpha.cli import app as cli_app
from vnalpha.data_availability.artifact_readiness_models import ReadinessCapability
from vnalpha.data_availability.policy import DataAvailabilityPolicy
from vnalpha.data_provisioning.current_symbol_application import (
    CurrentSymbolProvisioningState,
    CurrentSymbolResearchApplication,
    CurrentSymbolResearchRequest,
    CurrentSymbolResearchStatus,
    CurrentSymbolWaitMode,
)
from vnalpha.features.status import FEATURE_STATUS_CONTRACT_VERSION
from vnalpha.provisioning_queue import ProvisioningQueue
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
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
            "VALUES (?, ?, '1D', 10.0, 'test', 'pass')",
            [
                (symbol, (target_date - timedelta(days=offset)).isoformat())
                for symbol in ("FPT", "VNINDEX")
                for offset in range(5)
            ],
        )
        _seed_ranking_evidence(connection, target_date.isoformat())
    with duckdb.connect(str(warehouse_path), read_only=True) as connection:
        before = connection.execute("SELECT COUNT(*) FROM canonical_ohlcv").fetchone()[
            0
        ]

    application = CurrentSymbolResearchApplication(
        warehouse_path=warehouse_path,
        queue_path=tmp_path / "provisioning.sqlite3",
        policy=DataAvailabilityPolicy(min_required_bars=1),
    )
    result = application.execute(
        CurrentSymbolResearchRequest(
            symbol="FPT",
            effective_date=target_date.isoformat(),
            requested_capability=ReadinessCapability.PRICE_ANALYSIS,
        )
    )
    ranking = application.execute(
        CurrentSymbolResearchRequest(
            symbol="FPT",
            effective_date=target_date.isoformat(),
            requested_capability=ReadinessCapability.CANDIDATE_RANKING,
        )
    )
    repeated = application.execute(
        CurrentSymbolResearchRequest(
            symbol="FPT",
            effective_date=target_date.isoformat(),
            requested_capability=ReadinessCapability.PRICE_ANALYSIS,
        )
    )

    with duckdb.connect(str(warehouse_path), read_only=True) as connection:
        after = connection.execute("SELECT COUNT(*) FROM canonical_ohlcv").fetchone()[0]
    assert result.status is CurrentSymbolResearchStatus.READY
    assert result.requested_date == target_date.isoformat()
    assert result.effective_date == target_date.isoformat()
    assert result.job_id is None
    assert result.provisioning is CurrentSymbolProvisioningState.REUSED
    assert result.reused_fresh_data is True
    assert result.correlation_id
    assert result.readiness.requested_ready
    assert ranking.status is CurrentSymbolResearchStatus.READY
    assert ranking.effective_capability is ReadinessCapability.CANDIDATE_RANKING
    assert ranking.job_id is None
    assert ranking.provisioning is CurrentSymbolProvisioningState.REUSED
    assert ranking.reused_fresh_data is True
    assert repeated.provisioning is CurrentSymbolProvisioningState.REUSED
    assert before == after
    assert not (tmp_path / "provisioning.sqlite3").exists()


def _seed_ranking_evidence(
    connection: duckdb.DuckDBPyConnection, date_value: str
) -> None:
    lineage = json.dumps(
        {
            "feature_status_contract_version": FEATURE_STATUS_CONTRACT_VERSION,
            "benchmark_symbol": "VNINDEX",
            "selected_provider": "test",
            "ingestion_run_id": "test-run",
        }
    )
    connection.execute(
        """
        INSERT INTO feature_snapshot
        (symbol, date, close, ma20, as_of_bar_date, feature_data_status,
         feature_build_version, feature_generated_at, feature_profile,
         neutral_completeness, relative_strength_completeness,
         required_bar_count, observed_bar_count, feature_completeness_rule_version,
         lineage_json)
        VALUES ('FPT', ?, 10.0, 10.0, ?, 'EXACT_DATE', 'test-v1', current_timestamp,
                'STANDARD_120', 'COMPLETE', 'COMPLETE', 120, 120,
                'feature-completeness-v1', ?)
        """,
        [date_value, date_value, lineage],
    )
    connection.executemany(
        """
        INSERT INTO relative_strength_snapshot
        (symbol, date, benchmark_symbol, horizon_sessions, relative_return,
         source_bar_date, benchmark_bar_date, source_row_count,
         benchmark_row_count, data_status, methodology_version, generated_at,
         lineage_json)
        VALUES ('FPT', ?, 'VNINDEX', ?, 0.1, ?, ?, 120, 120,
                'SUCCESS', 'test-v1', current_timestamp, ?)
        """,
        [
            (date_value, horizon, date_value, date_value, lineage)
            for horizon in (20, 60)
        ],
    )
    score_lineage = json.dumps(
        {
            "as_of_bar_date": date_value,
            "scoring_version": "test-v1",
            "feature_build_version": "test-v1",
            "selected_provider": "test",
            "ingestion_run_id": "test-run",
            "scoring_policy_id": BASELINE_SCORING_POLICY.policy_id,
            "scoring_policy_version": BASELINE_SCORING_POLICY.version,
            "scoring_policy_hash": BASELINE_SCORING_POLICY.payload_hash,
            "scoring_policy_status": BASELINE_SCORING_POLICY.lifecycle_status.value,
        }
    )
    connection.execute(
        """
        INSERT INTO candidate_score
        (symbol, date, score, candidate_class, evidence_json, risk_flags_json,
         lineage_json, scoring_policy_id, scoring_policy_version,
         scoring_policy_hash, scoring_policy_status)
        VALUES ('FPT', ?, 0.75, 'STRONG_CANDIDATE', '{}', '[]', ?, ?, ?, ?, ?)
        """,
        [
            date_value,
            score_lineage,
            BASELINE_SCORING_POLICY.policy_id,
            BASELINE_SCORING_POLICY.version,
            BASELINE_SCORING_POLICY.payload_hash,
            BASELINE_SCORING_POLICY.lifecycle_status.value,
        ],
    )


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

    runner = CliRunner()
    warning = runner.invoke(
        cli_app,
        ["jobs", "cancel", str(job.job_id), "--queue-path", str(queue_path)],
    )
    assert warning.exit_code == 2
    assert "can affect every caller sharing this active job" in warning.output
    assert ProvisioningQueue(queue_path).get(job.job_id).status.value == "QUEUED"

    cancelled = runner.invoke(
        cli_app,
        [
            "jobs",
            "cancel",
            str(job.job_id),
            "--queue-path",
            str(queue_path),
            "--confirm",
        ],
    )
    assert cancelled.exit_code == 0
    repeated_cancel = runner.invoke(
        cli_app,
        [
            "jobs",
            "cancel",
            str(job.job_id),
            "--queue-path",
            str(queue_path),
            "--confirm",
        ],
    )
    assert repeated_cancel.exit_code == 1
    assert (
        "Jobs command failed: provisioning job is already terminal"
        in repeated_cancel.output
    )
    retry = runner.invoke(
        cli_app,
        [
            "jobs",
            "retry",
            str(job.job_id),
            "--queue-path",
            str(queue_path),
            "--json",
        ],
    )
    assert retry.exit_code == 0
    assert json.loads(retry.output)["job_id"] != str(job.job_id)
