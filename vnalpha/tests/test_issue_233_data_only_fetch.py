from __future__ import annotations

from dataclasses import replace

import duckdb
import pytest

import vnalpha.data_provisioning.data_only_symbol as data_only_module
import vnalpha.data_provisioning.ensure_current_symbol as ensure_module
from vnalpha.data_provisioning.ensure_current_symbol import (
    ProvisioningOutcome,
    ensure_current_symbol_ready,
)
from vnalpha.data_provisioning.service import (
    DataProvisioningResult,
    ProvisioningStatus,
)
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection)
    yield connection
    connection.close()


def test_data_only_fetch_downloads_ohlcv_and_builds_canonical_without_readiness(
    conn, monkeypatch
) -> None:
    # Given: deterministic OHLCV and canonical stages succeed while deep readiness
    # must not be consulted for a fetch_data plan.
    requests = []

    class FakeProvisioningService:
        def __init__(self, _conn: duckdb.DuckDBPyConnection) -> None:
            pass

        def execute(self, request):
            requests.append(request)
            base = DataProvisioningResult(
                status=ProvisioningStatus.SUCCESS,
                operation=request.operation,
                artifact=request.artifact,
                correlation_id="corr-233",
                resolved_date=request.date,
                symbol=request.symbol,
            )
            if request.artifact == "ohlcv":
                return replace(base, counts={"success": 1, "inserted": 3})
            return replace(base, counts={"upserted": 3, "rejected": 0})

    class ForbiddenDeepReadiness:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("fetch_data must not construct deep readiness")

    monkeypatch.setattr(
        data_only_module, "DataProvisioningService", FakeProvisioningService
    )
    monkeypatch.setattr(
        ensure_module, "DeepAnalysisReadinessService", ForbiddenDeepReadiness
    )

    # When: the shared operation is invoked in data-only mode.
    result = ensure_current_symbol_ready(
        conn,
        "FPT",
        "2026-07-17",
        refresh=True,
        data_only=True,
    )

    # Then: only the bounded data stages run and report readiness for fetch_data.
    assert [(item.operation, item.artifact) for item in requests] == [
        ("download", "ohlcv"),
        ("build", "canonical"),
    ]
    assert requests[0].symbol == "FPT"
    assert requests[0].symbols == ("FPT",)
    assert requests[0].start == "2025-05-23"
    assert requests[0].end == "2026-07-17"
    assert requests[1].symbol == "FPT"
    assert result.outcome is ProvisioningOutcome.REFRESHED
    assert [action.action for action in result.actions] == [
        "sync_ohlcv",
        "build_canonical",
    ]
    assert result.is_ready is True


def test_data_only_fetch_fails_closed_before_canonical_on_download_failure(
    conn, monkeypatch
) -> None:
    requests = []

    class FailedProvisioningService:
        def __init__(self, _conn: duckdb.DuckDBPyConnection) -> None:
            pass

        def execute(self, request):
            requests.append(request)
            return DataProvisioningResult(
                status=ProvisioningStatus.FAILED,
                operation=request.operation,
                artifact=request.artifact,
                correlation_id="corr-233-failed",
                resolved_date=request.date,
                symbol=request.symbol,
                error="Bounded OHLCV download failed.",
                follow_up="Retry the bounded symbol request.",
            )

    monkeypatch.setattr(
        data_only_module, "DataProvisioningService", FailedProvisioningService
    )

    result = ensure_current_symbol_ready(
        conn,
        "FPT",
        "2026-07-17",
        refresh=True,
        data_only=True,
    )

    assert [(item.operation, item.artifact) for item in requests] == [
        ("download", "ohlcv")
    ]
    assert result.outcome is ProvisioningOutcome.FAILED
    assert result.is_ready is False
    assert result.errors == ("Bounded OHLCV download failed.",)
    assert result.remediation == ("Retry the bounded symbol request.",)


def test_data_only_fetch_returns_typed_remediation_on_canonical_failure(
    conn, monkeypatch
) -> None:
    requests = []

    class CanonicalFailureService:
        def __init__(self, _conn: duckdb.DuckDBPyConnection) -> None:
            pass

        def execute(self, request):
            requests.append(request)
            if request.artifact == "ohlcv":
                return DataProvisioningResult(
                    status=ProvisioningStatus.SUCCESS,
                    operation=request.operation,
                    artifact=request.artifact,
                    correlation_id="corr-233-canonical",
                    counts={"success": 1, "inserted": 3},
                )
            return DataProvisioningResult(
                status=ProvisioningStatus.FAILED,
                operation=request.operation,
                artifact=request.artifact,
                correlation_id="corr-233-canonical",
                counts={"upserted": 0, "rejected": 3},
                error="Canonical validation rejected the downloaded rows.",
                follow_up="Inspect canonical rejection evidence, then retry.",
            )

    monkeypatch.setattr(
        data_only_module, "DataProvisioningService", CanonicalFailureService
    )

    result = ensure_current_symbol_ready(
        conn,
        "FPT",
        "2026-07-17",
        refresh=True,
        data_only=True,
    )

    assert [(item.operation, item.artifact) for item in requests] == [
        ("download", "ohlcv"),
        ("build", "canonical"),
    ]
    assert result.outcome is ProvisioningOutcome.FAILED
    assert result.is_ready is False
    assert result.errors == ("Canonical validation rejected the downloaded rows.",)
    assert result.remediation == ("Inspect canonical rejection evidence, then retry.",)
