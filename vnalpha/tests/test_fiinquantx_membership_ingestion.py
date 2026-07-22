from __future__ import annotations

import duckdb
import pytest

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.clients.vnstock.schemas import MembershipResponse, ResponseMeta
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
