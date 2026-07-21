from __future__ import annotations

import duckdb
import pytest

from vnalpha.clients.vnstock.errors import VnstockHTTPError
from vnalpha.clients.vnstock.schemas import ResponseMeta, VnstockResponse
from vnalpha.warehouse.migrations import run_migrations


class FakeCorporateActionClient:
    def __init__(self, rows: list[dict], provider: str = "VCI") -> None:
        self.rows = rows
        self.provider = provider

    def get_corporate_actions(self, **_: object) -> VnstockResponse:
        return VnstockResponse(
            data=self.rows,
            meta=ResponseMeta(
                dataset="reference.corporate_actions",
                provider=self.provider,
                quality_status="PASS",
            ),
        )

    def close(self) -> None:
        pass


class FailingCorporateActionClient:
    def __init__(self, *, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body

    def get_corporate_actions(self, **_: object) -> VnstockResponse:
        raise VnstockHTTPError(
            self.status_code, "/v1/reference/corporate-actions", self.body
        )

    def close(self) -> None:
        pass


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection)
    connection.execute(
        """
        INSERT INTO symbol_master
        (symbol, is_active, lifecycle_status, security_type)
        VALUES ('SSI', TRUE, 'ACTIVE', 'COMMON_EQUITY')
        """
    )
    return connection


def _cash_event(
    *,
    provider_event_id: str = "event-1",
    content_hash: str = "hash-1",
    cash_amount: float = 1_000,
) -> dict:
    return {
        "provider_event_id": provider_event_id,
        "symbol": "SSI",
        "action_type": "CASH_DIVIDEND",
        "announced_at": "2024-01-02",
        "ex_date": "2024-01-09",
        "record_date": "2024-01-10",
        "effective_date": "2024-01-20",
        "cash_amount": cash_amount,
        "ratio": None,
        "ratio_text": None,
        "subscription_price": None,
        "reference_price": None,
        "currency": "VND",
        "title": "Cash dividend",
        "provider": "VCI",
        "source_reference": f"vci://company/SSI/events/{provider_event_id}",
        "source_version": "corporate-actions-v1",
        "content_hash": content_hash,
        "source_payload_json": "{}",
        "quality_status": "NORMALIZED",
    }


def test_migrations_create_all_corporate_action_tables(conn) -> None:
    names = {
        row[0]
        for row in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
    }
    assert {
        "corporate_action_raw_evidence",
        "corporate_action",
        "corporate_action_source_link",
        "corporate_action_quarantine",
        "corporate_action_affected_range",
    } <= names
