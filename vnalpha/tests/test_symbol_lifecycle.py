"""Regression coverage for symbol lifecycle and taxonomy snapshots."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import duckdb
import pytest

from vnalpha.data_provisioning.service import (
    DataProvisioningDependencies,
    DataProvisioningRequest,
    DataProvisioningService,
)
from vnalpha.ingestion.sync_symbols import sync_symbols
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    get_symbol_taxonomy_as_of,
    get_symbols_active,
)


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    """Provide a migrated in-memory warehouse."""

    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


class SnapshotClient:
    """A deterministic symbol-source client for lifecycle tests."""

    def __init__(
        self,
        records: list[dict[str, object]],
        *,
        provider: str = "VCI",
        dataset: str = "reference.symbols",
        quality_status: str | None = "PASS",
    ) -> None:
        self._response = SimpleNamespace(
            data=records,
            meta=SimpleNamespace(
                provider=provider,
                dataset=dataset,
                quality_status=quality_status,
            ),
        )

    def get_symbols(self, *, source: str | None = None) -> SimpleNamespace:
        return self._response

    def close(self) -> None:
        return None


def _common_equity(
    symbol: str,
    *,
    sector: str = "Technology",
    sector_code: str = "TECH",
    effective_from: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "symbol": symbol,
        "exchange": "HOSE",
        "name": f"{symbol} Corporation",
        "security_type": "common stock",
        "trading_status": "active",
        "sector": sector,
        "sector_code": sector_code,
        "industry": "Software",
        "industry_code": "SOFT",
        "taxonomy_name": "ICB",
        "taxonomy_version": "2026.1",
    }
    if effective_from is not None:
        record["classification_effective_from"] = effective_from
    return record


def test_sync_persists_typed_snapshot_membership_and_excludes_non_equities(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Only active common equities belong to the default research universe."""

    records = [
        _common_equity("FPT"),
        {
            **_common_equity("E1VFVN30"),
            "security_type": "ETF",
            "sector": "Fund",
            "sector_code": "FUND",
        },
        {
            **_common_equity("VNINDEX"),
            "security_type": "index",
            "sector": None,
            "sector_code": None,
        },
        {
            **_common_equity("VIC"),
            "trading_status": "suspended",
        },
    ]

    result = sync_symbols(conn, client=SnapshotClient(records))

    assert result["synced"] == 4
    assert result["errors"] == 0
    assert get_symbols_active(conn) == ["FPT"]
    current = conn.execute(
        """
        SELECT security_type, lifecycle_status, sector_code, taxonomy_name,
               taxonomy_version, last_seen_source_snapshot_id
        FROM symbol_master
        WHERE symbol = 'FPT'
        """
    ).fetchone()
    assert current is not None
    assert current[:5] == ("COMMON_EQUITY", "ACTIVE", "TECH", "ICB", "2026.1")
    assert current[5] == result["snapshot_id"]
    assert conn.execute(
        "SELECT symbol FROM symbol_source_membership ORDER BY symbol"
    ).fetchall() == [("E1VFVN30",), ("FPT",), ("VIC",), ("VNINDEX",)]


def test_authoritative_complete_snapshot_deactivates_only_unseen_source_members(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Completed authoritative snapshots reconcile membership deterministically."""

    sync_symbols(
        conn,
        client=SnapshotClient([_common_equity("FPT"), _common_equity("VNM")]),
        authoritative_snapshot=True,
    )

    result = sync_symbols(
        conn,
        client=SnapshotClient([_common_equity("FPT")]),
        authoritative_snapshot=True,
    )

    assert result["deactivated"] == 1
    assert get_symbols_active(conn) == ["FPT"]
    assert conn.execute(
        "SELECT lifecycle_status, is_active FROM symbol_master WHERE symbol = 'VNM'"
    ).fetchone() == ("INACTIVE", False)


def test_partial_snapshot_never_deactivates_unseen_symbols(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """A malformed source record leaves prior membership active and auditable."""

    sync_symbols(
        conn,
        client=SnapshotClient([_common_equity("FPT"), _common_equity("VNM")]),
        authoritative_snapshot=True,
    )

    result = sync_symbols(
        conn,
        client=SnapshotClient([_common_equity("FPT"), {"symbol": ""}]),
        authoritative_snapshot=True,
    )

    assert result["errors"] == 1
    assert result["deactivated"] == 0
    assert result["snapshot_status"] == "PARTIAL"
    assert get_symbols_active(conn) == ["FPT", "VNM"]


def test_failed_snapshot_never_deactivates_unseen_symbols(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Provider failure leaves the prior active universe untouched."""

    sync_symbols(
        conn,
        client=SnapshotClient([_common_equity("FPT"), _common_equity("VNM")]),
        authoritative_snapshot=True,
    )

    class FailingClient:
        def get_symbols(self, *, source: str | None = None) -> SimpleNamespace:
            raise RuntimeError("source unavailable")

        def close(self) -> None:
            return None

    with pytest.raises(RuntimeError, match="source unavailable"):
        sync_symbols(conn, client=FailingClient(), authoritative_snapshot=True)

    assert get_symbols_active(conn) == ["FPT", "VNM"]
    assert conn.execute(
        """
        SELECT snapshot_status, deactivated_count
        FROM symbol_source_snapshot
        ORDER BY started_at DESC
        LIMIT 1
        """
    ).fetchone() == ("FAILED", 0)


@pytest.mark.parametrize(
    ("provider", "dataset", "quality_status"),
    [
        ("KBS", "reference.symbols", "PASS"),
        ("VCI", "equity.ohlcv", "PASS"),
        ("VCI", "reference.symbols", "FAIL"),
        ("VCI", "reference.symbols", None),
    ],
)
def test_invalid_authoritative_envelope_never_deactivates_existing_symbols(
    conn: duckdb.DuckDBPyConnection,
    provider: str,
    dataset: str,
    quality_status: str | None,
) -> None:
    sync_symbols(
        conn,
        source="VCI",
        client=SnapshotClient([_common_equity("FPT"), _common_equity("VNM")]),
        authoritative_snapshot=True,
    )

    with pytest.raises(ValueError):
        sync_symbols(
            conn,
            source="VCI",
            client=SnapshotClient(
                [_common_equity("FPT")],
                provider=provider,
                dataset=dataset,
                quality_status=quality_status,
            ),
            authoritative_snapshot=True,
        )

    assert get_symbols_active(conn) == ["FPT", "VNM"]
    assert conn.execute(
        "SELECT snapshot_status, deactivated_count "
        "FROM symbol_source_snapshot ORDER BY started_at DESC LIMIT 1"
    ).fetchone() == ("FAILED", 0)


def test_empty_authoritative_snapshot_never_deactivates_existing_symbols(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    sync_symbols(
        conn,
        source="VCI",
        client=SnapshotClient([_common_equity("FPT"), _common_equity("VNM")]),
        authoritative_snapshot=True,
    )

    with pytest.raises(ValueError, match="empty"):
        sync_symbols(
            conn,
            source="VCI",
            client=SnapshotClient([]),
            authoritative_snapshot=True,
        )

    assert get_symbols_active(conn) == ["FPT", "VNM"]
    assert conn.execute(
        "SELECT snapshot_status, deactivated_count "
        "FROM symbol_source_snapshot ORDER BY started_at DESC LIMIT 1"
    ).fetchone() == ("FAILED", 0)


def test_terminal_update_failure_rolls_back_symbol_projection(
    conn: duckdb.DuckDBPyConnection, monkeypatch
) -> None:
    from vnalpha.ingestion import sync_symbols as module

    original_finish = module.finish_ingestion_run

    def fail_success(connection, run_id, status, **kwargs):
        if status != "FAILED":
            raise RuntimeError("terminal update failed")
        return original_finish(connection, run_id, status, **kwargs)

    monkeypatch.setattr(module, "finish_ingestion_run", fail_success)

    with pytest.raises(RuntimeError, match="terminal update failed"):
        sync_symbols(
            conn,
            client=SnapshotClient([_common_equity("FPT")]),
        )

    assert conn.execute(
        "SELECT COUNT(*) FROM symbol_master WHERE symbol = 'FPT'"
    ).fetchone() == (0,)
    assert conn.execute(
        "SELECT snapshot_status FROM symbol_source_snapshot"
    ).fetchone() == ("FAILED",)
    assert conn.execute("SELECT status FROM ingestion_run").fetchone() == ("FAILED",)


def test_taxonomy_changes_are_available_as_of_their_snapshot_dates(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Sector history remains reproducible after a taxonomy reclassification."""

    sync_symbols(
        conn,
        client=SnapshotClient(
            [_common_equity("FPT", sector="Technology", effective_from="2026-01-01")]
        ),
    )
    sync_symbols(
        conn,
        client=SnapshotClient(
            [_common_equity("FPT", sector="Industrials", effective_from="2026-02-01")]
        ),
    )

    january = get_symbol_taxonomy_as_of(conn, "FPT", date(2026, 1, 15))
    february = get_symbol_taxonomy_as_of(conn, "FPT", date(2026, 2, 15))

    assert january is not None
    assert february is not None
    assert january.sector_name == "Technology"
    assert february.sector_name == "Industrials"


def test_provisioning_forwards_explicit_authoritative_snapshot(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """The CLI-facing provisioning boundary preserves explicit reconciliation intent."""

    observed: dict[str, object] = {}

    def fake_sync(
        _conn: duckdb.DuckDBPyConnection, **kwargs: object
    ) -> dict[str, object]:
        observed.update(kwargs)
        return {"synced": 1, "errors": 0}

    result = DataProvisioningService(
        conn,
        dependencies=DataProvisioningDependencies(sync_symbols=fake_sync),
    ).execute(
        DataProvisioningRequest(
            "download",
            "symbols",
            authoritative_snapshot=True,
        )
    )

    assert result.counts == {"synced": 1, "errors": 0}
    assert observed == {"source": None, "authoritative_snapshot": True}


def test_snapshot_audit_events_share_the_callers_correlation(
    conn: duckdb.DuckDBPyConnection,
    tmp_path,
) -> None:
    """Snapshot evidence records a correlated start and terminal outcome."""

    from vnalpha.observability.context import (
        init_run_context,
        reset_run_context,
        set_correlation_id,
    )

    reset_run_context()
    run_context = init_run_context("test", actor="test", log_root=tmp_path)
    correlation_id = set_correlation_id()
    try:
        sync_symbols(conn, client=SnapshotClient([_common_equity("FPT")]))
        events = [
            json.loads(line)
            for line in run_context.audit_path.read_text().splitlines()
            if line.strip()
        ]
        snapshot_events = [
            event
            for event in events
            if event["event_type"].startswith("SYMBOL_SNAPSHOT_")
        ]
        assert [event["event_type"] for event in snapshot_events] == [
            "SYMBOL_SNAPSHOT_STARTED",
            "SYMBOL_SNAPSHOT_COMPLETED",
        ]
        assert {event["correlation_id"] for event in snapshot_events} == {
            correlation_id
        }
    finally:
        reset_run_context()
