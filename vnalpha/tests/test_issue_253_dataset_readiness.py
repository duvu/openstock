"""Tests for issue #253: Dataset readiness and source policy."""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.data_availability.dataset_readiness import (
    DatasetReadinessStatus,
    check_dataset_readiness,
)
from vnalpha.data_provisioning.source_policy import (
    SourcePolicyResolver,
    SourceSelectionMode,
    get_default_resolver,
)


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    # Create minimal schema for testing
    connection.execute(
        "CREATE TABLE canonical_ohlcv (provider VARCHAR, time TIMESTAMP, close DOUBLE)"
    )
    connection.execute(
        "INSERT INTO canonical_ohlcv VALUES ('vci', '2026-07-17', 100.0)"
    )
    yield connection
    connection.close()


def test_reference_symbols_readiness(conn) -> None:
    # When: checking reference.symbols readiness
    result = check_dataset_readiness(conn, "reference.symbols")

    # Then: recognized as supported dataset
    assert result.dataset == "reference.symbols"
    assert result.status in (
        DatasetReadinessStatus.READY,
        DatasetReadinessStatus.NOT_READY,
    )


def test_unsupported_dataset_returns_not_ready(conn) -> None:
    # When: checking unsupported dataset
    result = check_dataset_readiness(conn, "unsupported.dataset")

    # Then: not ready with clear message
    assert result.status == DatasetReadinessStatus.NOT_READY
    assert "unsupported_dataset" in result.rejection_reasons
    assert "not supported" in result.message


def test_fiinquantx_is_explicit_only(conn) -> None:
    # When: checking equity.ohlcv readiness
    result = check_dataset_readiness(conn, "equity.ohlcv")

    # Then: FiinQuantX appears as explicit-only or in rejections
    # (depends on whether SDK is installed)
    assert "fiinquantx" in result.explicit_providers or any(
        "fiinquantx" in r for r in result.rejection_reasons
    )


def test_source_policy_explicit_request_no_fallback() -> None:
    # Given: a resolver
    resolver = SourcePolicyResolver()

    # When: user explicitly requests a source
    resolved = resolver.resolve("equity.ohlcv", requested_source="fiinquantx")

    # Then: explicit mode with no fallback
    assert resolved.source == "fiinquantx"
    assert resolved.mode == SourceSelectionMode.EXPLICIT
    assert resolved.fallback_allowed is False
    assert "explicitly" in resolved.rationale


def test_source_policy_reference_symbols_auto_only() -> None:
    # Given: a resolver with default source
    resolver = SourcePolicyResolver(default_source="fiinquantx")

    # When: resolving reference.symbols
    resolved = resolver.resolve("reference.symbols")

    # Then: auto-routing regardless of default (FiinQuantX not used for reference)
    assert resolved.mode == SourceSelectionMode.AUTO
    assert resolved.fallback_allowed is True
    assert "auto-routing" in resolved.rationale.lower()


def test_source_policy_ohlcv_uses_default() -> None:
    # Given: a resolver with default source
    resolver = SourcePolicyResolver(default_source="vci", allow_auto_fallback=False)

    # When: resolving equity.ohlcv without explicit request
    resolved = resolver.resolve("equity.ohlcv")

    # Then: uses default with configured policy
    assert resolved.source == "vci"
    assert resolved.mode == SourceSelectionMode.CONFIGURED
    assert resolved.fallback_allowed is False


def test_source_policy_ohlcv_auto_when_no_default() -> None:
    # Given: resolver with no default
    resolver = SourcePolicyResolver()

    # When: resolving equity.ohlcv
    resolved = resolver.resolve("equity.ohlcv")

    # Then: auto-routing enabled
    assert resolved.mode == SourceSelectionMode.AUTO
    assert resolved.fallback_allowed is True


def test_source_policy_membership_requires_vci() -> None:
    # Given: a resolver
    resolver = SourcePolicyResolver()

    # When: resolving membership datasets
    index_resolved = resolver.resolve("index.membership")
    sector_resolved = resolver.resolve("sector.membership")

    # Then: VCI required, no fallback
    assert index_resolved.source == "vci"
    assert index_resolved.fallback_allowed is False
    assert sector_resolved.source == "vci"
    assert sector_resolved.fallback_allowed is False


def test_validate_fiinquantx_not_allowed_for_reference() -> None:
    # Given: a resolver
    resolver = SourcePolicyResolver()

    # When: validating FiinQuantX for reference.symbols
    is_valid, reason = resolver.validate_source_for_dataset(
        "reference.symbols", "fiinquantx"
    )

    # Then: rejected
    assert not is_valid
    assert "cannot be used" in reason


def test_validate_fiinquantx_allowed_for_ohlcv() -> None:
    # Given: a resolver
    resolver = SourcePolicyResolver()

    # When: validating FiinQuantX for OHLCV
    is_valid, reason = resolver.validate_source_for_dataset(
        "equity.ohlcv", "fiinquantx"
    )

    # Then: allowed as explicit-only
    assert is_valid
    assert "supports" in reason


def test_validate_free_providers_allowed() -> None:
    # Given: a resolver
    resolver = SourcePolicyResolver()

    # When: validating free providers
    for source in ("vci", "kbs", "ssi"):
        is_valid, reason = resolver.validate_source_for_dataset("equity.ohlcv", source)
        # Then: all allowed
        assert is_valid


def test_default_resolver_has_auto_routing() -> None:
    # When: getting default resolver
    resolver = get_default_resolver()

    # Then: auto-routing enabled
    assert resolver.default_source is None
    assert resolver.allow_auto_fallback is True


def test_resolved_source_preserves_rationale() -> None:
    # Given: various resolutions
    resolver = SourcePolicyResolver(default_source="vci")

    # When: resolving with different modes
    auto = resolver.resolve("reference.symbols")
    explicit = resolver.resolve("equity.ohlcv", requested_source="kbs")
    configured = resolver.resolve("index.membership")

    # Then: each has descriptive rationale
    assert len(auto.rationale) > 10
    assert len(explicit.rationale) > 10
    assert len(configured.rationale) > 10
    assert "auto" in auto.rationale.lower() or "routing" in auto.rationale.lower()
    assert (
        "explicit" in explicit.rationale.lower()
        or "requested" in explicit.rationale.lower()
    )


def test_readiness_degraded_when_only_explicit_provider(monkeypatch) -> None:
    # Given: no auto-route data present but the explicit-only provider configured.
    import duckdb

    from vnalpha.data_availability import dataset_readiness

    connection = duckdb.connect(":memory:")
    connection.execute(
        "CREATE TABLE canonical_ohlcv (provider VARCHAR, time TIMESTAMP, close DOUBLE)"
    )
    monkeypatch.setattr(
        dataset_readiness, "_is_provider_configured", lambda provider: True
    )
    try:
        result = dataset_readiness.check_dataset_readiness(connection, "equity.ohlcv")
    finally:
        connection.close()

    # Then: process is alive but the auto data path is not usable -> DEGRADED,
    # distinct from a hard NOT_READY.
    assert result.status is DatasetReadinessStatus.DEGRADED
    assert "fiinquantx" in result.explicit_providers
    assert not result.auto_providers
    assert "explicit-only" in (result.message or "")


def test_maintenance_records_resolved_source_policy() -> None:
    # Given: a persisted run with the resolved source policy attached (issue #253).
    import duckdb

    from vnalpha.cli_app.maintain import _resolve_source_policy
    from vnalpha.maintenance.ledger import (
        get_latest_maintenance_run,
        persist_maintenance_run,
    )
    from vnalpha.maintenance.models import (
        DailyMaintenanceResult,
        MaintenanceRunStatus,
        MaintenanceStageResult,
        MaintenanceStageStatus,
    )
    from vnalpha.warehouse.migrations import run_migrations

    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn, emit_observability=False)
    result = DailyMaintenanceResult(
        status=MaintenanceRunStatus.SUCCESS,
        requested_date="2026-07-17",
        resolved_date="2026-07-17",
        correlation_id="policy-test",
        stages=(
            MaintenanceStageResult("resolve_session", MaintenanceStageStatus.SUCCESS),
        ),
        requested_symbols=("VCB",),
        successful_symbols=("VCB",),
        failed_symbols=(),
        diagnostics_refs=(),
        mutated=True,
    )
    from datetime import datetime, timezone

    try:
        persist_maintenance_run(
            conn,
            result,
            started_at=datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 7, 17, 8, 1, tzinfo=timezone.utc),
            software_version="test",
            source_policy=_resolve_source_policy(None),
        )
        latest = get_latest_maintenance_run(conn)
    finally:
        conn.close()

    policy = latest["source_policy"]
    assert policy is not None
    # reference.symbols never resolves to an explicit source; OHLCV auto-routes.
    assert policy["reference.symbols"]["source"] is None
    assert policy["reference.symbols"]["mode"] == "AUTO"
    assert policy["equity.ohlcv"]["mode"] == "AUTO"


def test_explicit_source_recorded_without_silent_fallback() -> None:
    # Given: an explicit FiinQuantX source request for maintenance.
    from vnalpha.cli_app.maintain import _resolve_source_policy

    policy = _resolve_source_policy("fiinquantx")

    # Then: OHLCV records the explicit source with fallback disabled.
    assert policy["equity.ohlcv"]["source"] == "fiinquantx"
    assert policy["equity.ohlcv"]["mode"] == "EXPLICIT"
    assert policy["equity.ohlcv"]["fallback_allowed"] is False


def test_cli_and_worker_resolve_same_policy() -> None:
    # The CLI maintenance path and the shared resolver must agree (issue #253:
    # CLI, service and worker resolve the same source policy).
    from vnalpha.cli_app.maintain import _resolve_source_policy
    from vnalpha.data_provisioning.source_policy import get_default_resolver

    cli_policy = _resolve_source_policy(None)
    resolver = get_default_resolver()
    for dataset, recorded in cli_policy.items():
        resolved = resolver.resolve(dataset)
        assert recorded["source"] == resolved.source
        assert recorded["mode"] == resolved.mode.value
        assert recorded["fallback_allowed"] == resolved.fallback_allowed


def test_maintain_readiness_cli_reports_datasets() -> None:
    from typer.testing import CliRunner

    from vnalpha.cli import app

    result = CliRunner().invoke(app, ["maintain", "readiness", "--json"])
    assert result.exit_code == 0
    import json as _json

    payload = _json.loads(result.stdout)
    datasets = {d["dataset"] for d in payload["datasets"]}
    assert "reference.symbols" in datasets
    assert "equity.ohlcv" in datasets
    # reference.symbols must never advertise FiinQuantX.
    ref = next(d for d in payload["datasets"] if d["dataset"] == "reference.symbols")
    assert "fiinquantx" not in ref["explicit_providers"]
