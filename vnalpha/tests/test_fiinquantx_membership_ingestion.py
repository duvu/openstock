from __future__ import annotations

import json

import duckdb
import pytest
from typer.testing import CliRunner

from vnalpha.cli_app.sync import app as sync_app
from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.clients.vnstock.schemas import MembershipResponse, ResponseMeta
from vnalpha.ingestion.sync_membership import (
    MembershipSyncResult,
    MembershipSyncStatus,
    sync_membership,
)
from vnalpha.ingestion.sync_symbols import sync_symbols
from vnalpha.warehouse.migrations import run_migrations


def _response(
    *,
    dataset: str = "reference.index_membership_snapshot",
    entity_id: str = "VN30",
    members: tuple[str, ...] = ("FPT", "VNM"),
) -> MembershipResponse:
    return MembershipResponse(
        data=[
            {
                "entity_id": entity_id,
                "member_symbol": member,
                "observed_at": "2026-07-16T08:30:00Z",
            }
            for member in members
        ],
        meta=ResponseMeta(
            request_id="req-membership-1",
            dataset=dataset,
            provider="FIINQUANTX",
            quality_status="PASS",
            fetched_at="2026-07-16T08:30:01Z",
        ),
        diagnostics={
            "provider_lineage": {
                "sdk_version": "0.1.64",
                "contract_version": "fiinquantx-0.1.64-v1",
                "source_method": "TickerList",
                "snapshot_semantics": "observed_current_membership",
                "password": "must-not-persist",
            },
            "password": "must-not-persist",
        },
    )


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection, emit_observability=False)
    return connection


@pytest.fixture(autouse=True)
def approved_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED", "true")


def test_client_requests_typed_membership_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = object.__new__(VnstockClient)
    calls: list[tuple[str, dict[str, str] | None]] = []

    def fake_get(path: str, params: dict[str, str] | None = None):
        calls.append((path, params))
        dataset = (
            "reference.index_membership_snapshot"
            if "index" in path
            else "reference.sector_membership_snapshot"
        )
        return _response(dataset=dataset).model_dump(mode="json")

    monkeypatch.setattr(client, "_get", fake_get)

    assert client.get_index_membership("vn30", source="fiinquantx").data
    assert client.get_sector_membership("icb-8300", source="fiinquantx").data
    assert calls == [
        (
            "/v1/reference/index-membership",
            {
                "symbol": "VN30",
                "source": "FIINQUANTX",
                "validate": "true",
                "quality_mode": "strict",
            },
        ),
        (
            "/v1/reference/sector-membership",
            {
                "symbol": "ICB-8300",
                "source": "FIINQUANTX",
                "validate": "true",
                "quality_mode": "strict",
            },
        ),
    ]


def test_membership_sync_persists_current_snapshot_and_safe_lineage(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    class Client:
        def get_index_membership(self, entity_id: str, source: str | None = None):
            assert (entity_id, source) == ("VN30", "FIINQUANTX")
            return _response()

    result = sync_membership(
        conn,
        membership_type="index",
        entity_id="vn30",
        source="fiinquantx",
        client=Client(),
    )

    assert result.status is MembershipSyncStatus.SUCCESS
    assert result.member_count == 2
    snapshot = conn.execute(
        "SELECT dataset, membership_type, entity_id, provider, source_query, "
        "snapshot_semantics, member_count, status, lineage_json, diagnostics_json "
        "FROM reference_membership_snapshot"
    ).fetchone()
    assert snapshot[:8] == (
        "reference.index_membership_snapshot",
        "index",
        "VN30",
        "FIINQUANTX",
        "VN30",
        "observed_current_membership",
        2,
        "SUCCESS",
    )
    persisted = json.loads(snapshot[8]) | json.loads(snapshot[9])
    serialized = json.dumps(persisted, sort_keys=True)
    assert persisted["source_method"] == "TickerList"
    assert "approval_reference" not in serialized
    assert "approval_fingerprint" not in serialized
    assert "password" not in serialized
    assert conn.execute(
        "SELECT member_symbol FROM reference_membership_member ORDER BY member_symbol"
    ).fetchall() == [("FPT",), ("VNM",)]


def test_membership_sync_persists_valid_empty_observation(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    class Client:
        def get_sector_membership(self, entity_id: str, source: str | None = None):
            return _response(
                dataset="reference.sector_membership_snapshot",
                entity_id=entity_id,
                members=(),
            )

    result = sync_membership(
        conn,
        membership_type="sector",
        entity_id="icb-8300",
        source="FIINQUANTX",
        client=Client(),
    )

    assert result.status is MembershipSyncStatus.EMPTY
    assert conn.execute(
        "SELECT entity_id, member_count, status, observed_at "
        "FROM reference_membership_snapshot"
    ).fetchone()[:3] == ("ICB-8300", 0, "EMPTY")
    assert (
        conn.execute("SELECT count(*) FROM reference_membership_member").fetchone()[0]
        == 0
    )


def test_membership_sync_fails_closed_without_partial_snapshot(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    class Client:
        def get_index_membership(self, entity_id: str, source: str | None = None):
            return _response(entity_id="VN100")

    result = sync_membership(
        conn,
        membership_type="index",
        entity_id="VN30",
        source="FIINQUANTX",
        client=Client(),
    )

    assert result.status is MembershipSyncStatus.FAILED
    assert result.error == "Provider membership response failed validation."
    assert (
        conn.execute("SELECT count(*) FROM reference_membership_snapshot").fetchone()[0]
        == 0
    )
    run = conn.execute(
        "SELECT status, error_json FROM ingestion_run WHERE ingestion_run_id = ?",
        [result.ingestion_run_id],
    ).fetchone()
    assert run[0] == "FAILED"
    assert "VN100" not in run[1]


def test_membership_failed_provider_quality_is_not_persisted(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    response = _response()
    response.meta.quality_status = "FAIL"

    class Client:
        def get_index_membership(self, entity_id: str, source: str | None = None):
            return response

    result = sync_membership(
        conn,
        membership_type="index",
        entity_id="VN30",
        source="FIINQUANTX",
        client=Client(),
    )

    assert result.status is MembershipSyncStatus.FAILED
    assert conn.execute(
        "SELECT COUNT(*) FROM reference_membership_snapshot"
    ).fetchone() == (0,)


def test_membership_missing_provider_quality_is_not_persisted(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    response = _response()
    response.meta.quality_status = None

    class Client:
        def get_index_membership(self, entity_id: str, source: str | None = None):
            return response

    result = sync_membership(
        conn,
        membership_type="index",
        entity_id="VN30",
        source="FIINQUANTX",
        client=Client(),
    )

    assert result.status is MembershipSyncStatus.FAILED
    assert conn.execute(
        "SELECT COUNT(*) FROM reference_membership_snapshot"
    ).fetchone() == (0,)


def test_membership_naive_observation_time_is_not_persisted(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    response = _response().model_copy(
        update={
            "data": [
                {**row, "observed_at": "2026-07-16T08:30:00"}
                for row in _response().data
            ]
        }
    )

    class Client:
        def get_index_membership(self, entity_id: str, source: str | None = None):
            return response

    result = sync_membership(
        conn,
        membership_type="index",
        entity_id="VN30",
        source="FIINQUANTX",
        client=Client(),
    )

    assert result.status is MembershipSyncStatus.FAILED
    assert conn.execute(
        "SELECT COUNT(*) FROM reference_membership_snapshot"
    ).fetchone() == (0,)


def test_actual_fiinquantx_provider_requires_approval_when_source_is_implicit(
    conn: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED")

    class Client:
        def get_index_membership(self, entity_id: str, source: str | None = None):
            assert source is None
            return _response()

    result = sync_membership(
        conn,
        membership_type="index",
        entity_id="VN30",
        client=Client(),
    )

    assert result.status is MembershipSyncStatus.FAILED
    assert conn.execute(
        "SELECT COUNT(*) FROM reference_membership_snapshot"
    ).fetchone() == (0,)


def test_membership_snapshot_rolls_back_when_terminal_run_update_fails(
    conn: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vnalpha.ingestion import sync_membership as module

    original_finish = module.finish_ingestion_run

    def fail_success(connection, run_id, status, error=None):
        if status == "SUCCESS":
            raise duckdb.TransactionException("terminal update failed")
        return original_finish(connection, run_id, status, error=error)

    monkeypatch.setattr(module, "finish_ingestion_run", fail_success)

    class Client:
        def get_index_membership(self, entity_id: str, source: str | None = None):
            return _response()

    result = sync_membership(
        conn,
        membership_type="index",
        entity_id="VN30",
        source="FIINQUANTX",
        client=Client(),
    )

    assert result.status is MembershipSyncStatus.FAILED
    assert conn.execute(
        "SELECT COUNT(*) FROM reference_membership_snapshot"
    ).fetchone() == (0,)


def test_membership_source_policy_rejects_before_creating_run(
    conn: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED")

    with pytest.raises(ValueError, match="FIINQUANTX persistence is disabled"):
        sync_membership(
            conn,
            membership_type="index",
            entity_id="VN30",
            source="FIINQUANTX",
            client=object(),
        )

    assert conn.execute("SELECT count(*) FROM ingestion_run").fetchone()[0] == 0


def test_symbol_bootstrap_rejects_fiinquantx_before_creating_run(
    conn: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED")

    with pytest.raises(ValueError, match="FIINQUANTX persistence is disabled"):
        sync_symbols(conn, source="FIINQUANTX", client=object())

    assert conn.execute("SELECT count(*) FROM ingestion_run").fetchone()[0] == 0


def test_membership_cli_exposes_truthful_terminal_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("vnalpha.warehouse.connection.get_connection", lambda: object())
    monkeypatch.setattr(
        "vnalpha.warehouse.migrations.run_migrations", lambda *, conn: None
    )
    monkeypatch.setattr(
        "vnalpha.ingestion.sync_membership.sync_membership",
        lambda *args, **kwargs: MembershipSyncResult(
            ingestion_run_id="run-1",
            snapshot_id="snapshot-1",
            status=MembershipSyncStatus.EMPTY,
            membership_type="sector",
            entity_id="ICB-8300",
        ),
    )

    result = CliRunner().invoke(
        sync_app,
        [
            "membership",
            "--type",
            "sector",
            "--entity",
            "icb-8300",
            "--source",
            "fiinquantx",
        ],
    )

    assert result.exit_code == 0
    assert "EMPTY" in result.stdout
    assert "0 members" in result.stdout


def test_membership_cli_validates_before_opening_warehouse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = False

    def get_connection():
        nonlocal opened
        opened = True
        return object()

    monkeypatch.setattr("vnalpha.warehouse.connection.get_connection", get_connection)

    result = CliRunner().invoke(
        sync_app,
        ["membership", "--type", "invalid", "--entity", "VN30"],
    )

    assert result.exit_code == 1
    assert opened is False
