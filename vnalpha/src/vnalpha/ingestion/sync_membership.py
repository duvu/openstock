from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

import duckdb
from pydantic import ValidationError

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.clients.vnstock.errors import (
    VnstockConnectionError,
    VnstockDataError,
    VnstockHTTPError,
    VnstockTimeoutError,
)
from vnalpha.clients.vnstock.schemas import MembershipResponse
from vnalpha.clients.vnstock.source_policy import validate_persistence_source
from vnalpha.ingestion.persistence import bind_ingestion_run_correlation
from vnalpha.observability.context import get_correlation_id, set_correlation_id
from vnalpha.warehouse.repositories import create_ingestion_run, finish_ingestion_run
from vnalpha.warehouse.transaction import warehouse_transaction

_DATASETS = {
    "index": "reference.index_membership_snapshot",
    "sector": "reference.sector_membership_snapshot",
}
_SAFE_LINEAGE_KEYS = frozenset(
    {
        "sdk_version",
        "contract_version",
        "source_method",
        "snapshot_semantics",
    }
)


class MembershipSyncStatus(str, Enum):
    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class MembershipSyncResult:
    ingestion_run_id: str
    status: MembershipSyncStatus
    membership_type: str
    entity_id: str
    member_count: int = 0
    snapshot_id: str | None = None
    error: str | None = None


class _MembershipClient(Protocol):
    def get_index_membership(
        self, entity_id: str, source: str | None = None
    ) -> MembershipResponse: ...

    def get_sector_membership(
        self, entity_id: str, source: str | None = None
    ) -> MembershipResponse: ...


def sync_membership(
    conn: duckdb.DuckDBPyConnection,
    *,
    membership_type: str,
    entity_id: str,
    source: str | None = None,
    client: _MembershipClient | None = None,
    base_url: str | None = None,
) -> MembershipSyncResult:
    normalized_type, normalized_entity, normalized_source = validate_membership_request(
        membership_type, entity_id, source
    )

    if get_correlation_id() in {"", "unset"}:
        set_correlation_id()

    endpoint = f"/v1/reference/{normalized_type}-membership"
    run_id = create_ingestion_run(
        conn,
        source_service="vnstock-service",
        source_endpoint=endpoint,
        universe=normalized_entity,
        params={
            "membership_type": normalized_type,
            "entity_id": normalized_entity,
            "source": normalized_source,
        },
    )
    bind_ingestion_run_correlation(conn, run_id)
    active_client = client
    owned = False
    try:
        if active_client is None:
            active_client = VnstockClient(base_url=base_url)
            owned = True
        fetch = getattr(active_client, f"get_{normalized_type}_membership")
        response = fetch(normalized_entity, source=normalized_source)
        return _persist_response(
            conn,
            run_id=run_id,
            membership_type=normalized_type,
            entity_id=normalized_entity,
            requested_source=normalized_source,
            response=response,
        )
    except (
        VnstockConnectionError,
        VnstockDataError,
        VnstockHTTPError,
        VnstockTimeoutError,
        ValidationError,
        ValueError,
        RuntimeError,
        duckdb.Error,
    ):
        finish_ingestion_run(
            conn,
            run_id,
            MembershipSyncStatus.FAILED.value,
            error={"error": "Provider membership response failed validation."},
        )
        return MembershipSyncResult(
            ingestion_run_id=run_id,
            status=MembershipSyncStatus.FAILED,
            membership_type=normalized_type,
            entity_id=normalized_entity,
            error="Provider membership response failed validation.",
        )
    finally:
        if owned and active_client is not None:
            active_client.close()


def validate_membership_request(
    membership_type: str,
    entity_id: str,
    source: str | None,
) -> tuple[str, str, str | None]:
    normalized_type = membership_type.strip().lower()
    if normalized_type not in _DATASETS:
        raise ValueError("membership_type must be 'index' or 'sector'")
    normalized_entity = entity_id.strip().upper()
    if not normalized_entity:
        raise ValueError("entity_id must not be empty")
    normalized_source = validate_persistence_source(source)
    return normalized_type, normalized_entity, normalized_source


def _persist_response(
    conn: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    membership_type: str,
    entity_id: str,
    requested_source: str | None,
    response: MembershipResponse,
) -> MembershipSyncResult:
    dataset = _DATASETS[membership_type]
    if response.meta.dataset != dataset:
        raise ValueError("unexpected membership dataset")
    provider = response.meta.provider.strip().upper()
    if not provider:
        raise ValueError("membership provider must not be empty")
    actual_source = validate_persistence_source(provider)
    if requested_source is not None and actual_source != requested_source:
        raise ValueError("membership provider did not match the selected source")
    quality_status = (response.meta.quality_status or "").strip().upper()
    if quality_status not in {"PASS", "SUCCESS"}:
        raise ValueError("membership provider quality did not pass")

    entity_ids = {str(row["entity_id"]).strip().upper() for row in response.data}
    if entity_ids and entity_ids != {entity_id}:
        raise ValueError("membership entity mismatch")
    members = tuple(dict.fromkeys(str(row["member_symbol"]) for row in response.data))
    observed_values = {
        _parse_aware_datetime(str(row["observed_at"])) for row in response.data
    }
    if len(observed_values) > 1:
        raise ValueError("membership observation timestamps differ")
    if observed_values:
        observed_at = next(iter(observed_values))
    elif response.meta.fetched_at:
        observed_at = _parse_aware_datetime(response.meta.fetched_at)
    else:
        raise ValueError("empty membership response lacks observation time")

    lineage = _safe_lineage(response.diagnostics)
    semantics = lineage.get("snapshot_semantics")
    if semantics != "observed_current_membership":
        raise ValueError("membership snapshot semantics are not current-observation")
    status = MembershipSyncStatus.SUCCESS if members else MembershipSyncStatus.EMPTY
    snapshot_id = f"{run_id}:{membership_type}:{entity_id}"
    correlation_id = get_correlation_id()
    with warehouse_transaction(conn):
        conn.execute(
            """
            INSERT INTO reference_membership_snapshot
            (snapshot_id, ingestion_run_id, dataset, membership_type, entity_id,
             observed_at, provider, source_query, member_count, status, request_id,
             fetched_at, snapshot_semantics, lineage_json, diagnostics_json,
             correlation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                snapshot_id,
                run_id,
                dataset,
                membership_type,
                entity_id,
                observed_at,
                provider,
                entity_id,
                len(members),
                status.value,
                response.meta.request_id,
                response.meta.fetched_at,
                semantics,
                json.dumps(lineage, sort_keys=True),
                json.dumps(lineage, sort_keys=True),
                correlation_id,
            ],
        )
        if members:
            conn.executemany(
                "INSERT INTO reference_membership_member "
                "(snapshot_id, member_symbol) VALUES (?, ?)",
                [(snapshot_id, member) for member in members],
            )
        finish_ingestion_run(conn, run_id, status.value)
    return MembershipSyncResult(
        ingestion_run_id=run_id,
        snapshot_id=snapshot_id,
        status=status,
        membership_type=membership_type,
        entity_id=entity_id,
        member_count=len(members),
    )


def _safe_lineage(
    diagnostics: dict[str, object],
) -> dict[str, str | int | float | bool]:
    raw_lineage = diagnostics.get("provider_lineage", {})
    if not isinstance(raw_lineage, dict):
        raw_lineage = {}
    return {
        key: value
        for key, value in raw_lineage.items()
        if key in _SAFE_LINEAGE_KEYS and isinstance(value, (str, int, float, bool))
    }


def _parse_aware_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("membership observation time must include a timezone")
    return parsed


__all__ = [
    "MembershipSyncResult",
    "MembershipSyncStatus",
    "sync_membership",
    "validate_membership_request",
]
