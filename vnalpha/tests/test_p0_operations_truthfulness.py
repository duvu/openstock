from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb
import pytest
from typer.testing import CliRunner

from vnalpha.cli_app import maintain as maintain_cli
from vnalpha.data_availability.dataset_readiness import (
    DatasetReadinessStatus,
    check_dataset_readiness,
)
from vnalpha.data_provisioning.source_policy import (
    InvalidSourceForDataset,
    SourcePolicyResolver,
)
from vnalpha.ingestion.trading_calendar import (
    CalendarCoverageError,
    SessionRange,
    VietnamSessionCalendar,
)
from vnalpha.maintenance.ledger import (
    collect_operational_proof,
    persist_maintenance_run,
)
from vnalpha.maintenance.models import (
    DailyMaintenanceResult,
    MaintenanceRunStatus,
    MaintenanceStageResult,
    MaintenanceStageStatus,
)
from vnalpha.maintenance.software_identity import SoftwareIdentity
from vnalpha.warehouse.migrations import run_migrations


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


def test_source_policy_rejects_invalid_explicit_dataset_source() -> None:
    resolver = SourcePolicyResolver()
    with pytest.raises(InvalidSourceForDataset):
        resolver.resolve("reference.symbols", requested_source="fiinquantx")


def test_dataset_readiness_uses_real_canonical_provider_column() -> None:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn, emit_observability=False)
    conn.execute(
        """
        INSERT INTO canonical_ohlcv (
            symbol, time, interval, close, selected_provider,
            price_basis, quality_status, ingestion_run_id
        ) VALUES ('FPT', '2026-07-17', '1D', 100, 'VCI',
                  'RAW_UNADJUSTED', 'PASS', 'run-1')
        """
    )
    result = check_dataset_readiness(conn, "equity.ohlcv")
    conn.close()
    assert result.status is DatasetReadinessStatus.READY
    assert "vci" in result.auto_providers


def test_dataset_readiness_uses_membership_snapshot_contract() -> None:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn, emit_observability=False)
    conn.execute(
        """
        INSERT INTO reference_membership_snapshot (
            snapshot_id, ingestion_run_id, dataset, membership_type, entity_id,
            observed_at, provider, source_query, member_count, status,
            snapshot_semantics, lineage_json, correlation_id
        ) VALUES (
            'snap-1', 'run-1', 'reference.index_membership_snapshot',
            'INDEX', 'VN30', current_timestamp, 'VCI', 'VN30', 30,
            'SUCCESS', 'observed_current_membership', '{}', 'corr-1'
        )
        """
    )
    result = check_dataset_readiness(conn, "reference.index_membership_snapshot")
    conn.close()
    assert result.status is DatasetReadinessStatus.READY
    assert result.auto_providers == ("vci",)


def test_calendar_resolution_fails_closed_outside_version() -> None:
    # The implicit session-resolution boundary fails closed outside the
    # versioned calendar coverage. Generic weekday/holiday primitives
    # (is_session, sessions) stay lenient for historical-range queries; the
    # fail-closed guarantee lives at latest_session_on_or_before and the
    # maintenance expiry guard.
    calendar = VietnamSessionCalendar()
    with pytest.raises(CalendarCoverageError):
        calendar.latest_session_on_or_before(date(2027, 1, 4))


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


def test_operational_proof_requires_consecutive_sessions_and_two_rerun_dates() -> None:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn, emit_observability=False)
    calendar = VietnamSessionCalendar()
    sessions = calendar.sessions(SessionRange(date(2026, 7, 6), date(2026, 7, 17)))
    assert len(sessions) == 10

    for index, session_date in enumerate(sessions):
        completed = datetime(
            session_date.year,
            session_date.month,
            session_date.day,
            10,
            tzinfo=timezone.utc,
        )
        persist_maintenance_run(
            conn,
            _maintenance_result(session_date, f"corr-{index}"),
            started_at=completed,
            completed_at=completed,
            software_version="vnalpha-1.0.0;commit=" + "b" * 40,
            package_version="1.0.0",
            source_commit="b" * 40,
            tree_state="clean",
            calendar_version=calendar.version,
            source_policy={"equity.ohlcv": {"mode": "AUTO"}},
        )
        if session_date in {sessions[2], sessions[7]}:
            persist_maintenance_run(
                conn,
                _maintenance_result(session_date, f"rerun-{index}"),
                started_at=completed,
                completed_at=completed,
                software_version="vnalpha-1.0.0;commit=" + "b" * 40,
                package_version="1.0.0",
                source_commit="b" * 40,
                tree_state="clean",
                calendar_version=calendar.version,
                source_policy={"equity.ohlcv": {"mode": "AUTO"}},
            )

    proof = collect_operational_proof(conn, calendar=calendar)
    conn.close()
    assert proof["consecutive_market_sessions"] is True
    assert len(proof["same_date_rerun_dates"]) == 2
    assert proof["has_required_sessions"] is True
