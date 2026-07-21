"""Regression coverage for symbol lifecycle and taxonomy snapshots."""

from __future__ import annotations

from types import SimpleNamespace

import duckdb
import pytest

from vnalpha.ingestion.sync_symbols import sync_symbols
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
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
