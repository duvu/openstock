from __future__ import annotations

from copy import deepcopy

import duckdb
import pytest

from vnalpha.clients.vnstock.errors import VnstockHTTPError
from vnalpha.clients.vnstock.schemas import ResponseMeta, VnstockResponse
from vnalpha.ingestion.corporate_actions import (
    corporate_action_status,
    sync_corporate_actions,
)
from vnalpha.warehouse.migrations import run_migrations


class FakeCorporateActionClient:
    def __init__(self, rows: list[dict], provider: str = "VCI") -> None:
        self.rows = rows
        self.provider = provider

    def get_corporate_actions(self, **_: object) -> VnstockResponse:
        return VnstockResponse(
            data=self.rows,
            meta=ResponseMeta(
                dataset="reference.corporate_actions", provider=self.provider
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


def test_repeated_ingestion_is_idempotent(conn) -> None:
    event = _cash_event()
    first = sync_corporate_actions(
        conn, symbol="SSI", client=FakeCorporateActionClient([event])
    )
    second = sync_corporate_actions(
        conn, symbol="SSI", client=FakeCorporateActionClient([event])
    )

    assert first["status"] == "COMPLETE"
    assert first["canonical_inserted"] == 1
    assert first["raw_inserted"] == 1
    assert second["unchanged"] == 1
    assert second["raw_inserted"] == 0
    assert conn.execute("SELECT COUNT(*) FROM corporate_action").fetchone()[0] == 1
    assert (
        conn.execute("SELECT COUNT(*) FROM corporate_action_raw_evidence").fetchone()[0]
        == 1
    )


def test_revision_preserves_history_and_emits_affected_range(conn) -> None:
    original = _cash_event()
    revised = _cash_event(content_hash="hash-2", cash_amount=1_200)

    sync_corporate_actions(
        conn, symbol="SSI", client=FakeCorporateActionClient([original])
    )
    result = sync_corporate_actions(
        conn, symbol="SSI", client=FakeCorporateActionClient([revised])
    )

    assert result["revised"] == 1
    rows = conn.execute(
        """
        SELECT revision_id, revision_number, canonical_status, cash_amount,
               supersedes_revision_id, superseded_by_revision_id
        FROM corporate_action ORDER BY revision_number
        """
    ).fetchall()
    assert [(row[1], row[2], row[3]) for row in rows] == [
        (1, "SUPERSEDED", 1_000.0),
        (2, "ACTIVE", 1_200.0),
    ]
    assert rows[0][5] == rows[1][0]
    assert rows[1][4] == rows[0][0]
    assert conn.execute(
        "SELECT reason, affected_from_date FROM corporate_action_affected_range ORDER BY created_at DESC LIMIT 1"
    ).fetchone() == (
        "REVISED_ACTION",
        duckdb.sql("SELECT DATE '2024-01-09'").fetchone()[0],
    )


def test_conflicting_provider_evidence_is_preserved_not_overwritten(conn) -> None:
    vci = _cash_event(cash_amount=1_000)
    kbs = deepcopy(vci)
    kbs.update(
        {
            "provider_event_id": "kbs-1",
            "provider": "KBS",
            "source_reference": "kbs://company/SSI/events/kbs-1",
            "content_hash": "kbs-hash",
            "cash_amount": 900,
        }
    )

    sync_corporate_actions(conn, symbol="SSI", client=FakeCorporateActionClient([vci]))
    result = sync_corporate_actions(
        conn, symbol="SSI", client=FakeCorporateActionClient([kbs], provider="KBS")
    )

    assert result["conflicts"] == 1
    assert result["status"] == "PARTIAL"
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM corporate_action WHERE canonical_status='CONFLICT'"
        ).fetchone()[0]
        == 2
    )
    assert sorted(
        row[0]
        for row in conn.execute("SELECT cash_amount FROM corporate_action").fetchall()
    ) == [900.0, 1_000.0]
    assert (
        conn.execute("SELECT COUNT(*) FROM corporate_action_source_link").fetchone()[0]
        == 2
    )


def test_source_revision_can_resolve_existing_cross_provider_conflict(conn) -> None:
    vci = _cash_event(cash_amount=1_000)
    kbs = deepcopy(vci)
    kbs.update(
        {
            "provider_event_id": "kbs-resolution",
            "provider": "KBS",
            "source_reference": "kbs://company/SSI/events/kbs-resolution",
            "content_hash": "kbs-resolution-hash",
            "cash_amount": 900,
        }
    )
    vci_revised = _cash_event(content_hash="vci-resolution-hash", cash_amount=900)

    sync_corporate_actions(conn, symbol="SSI", client=FakeCorporateActionClient([vci]))
    sync_corporate_actions(
        conn, symbol="SSI", client=FakeCorporateActionClient([kbs], provider="KBS")
    )
    result = sync_corporate_actions(
        conn, symbol="SSI", client=FakeCorporateActionClient([vci_revised])
    )

    assert result["status"] == "COMPLETE"
    assert result["revised"] == 1
    assert result["conflicts"] == 0
    rows = conn.execute(
        "SELECT cash_amount, canonical_status FROM corporate_action ORDER BY revision_number"
    ).fetchall()
    assert rows == [(1_000.0, "SUPERSEDED"), (900.0, "ACTIVE")]
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM corporate_action_source_link WHERE revision_id=(SELECT revision_id FROM corporate_action WHERE cash_amount=900)"
        ).fetchone()[0]
        == 2
    )


def test_source_revision_does_not_supersede_other_provider_conflict(conn) -> None:
    vci = _cash_event(cash_amount=1_000)
    kbs = deepcopy(vci)
    kbs.update(
        {
            "provider_event_id": "kbs-conflict",
            "provider": "KBS",
            "source_reference": "kbs://company/SSI/events/kbs-conflict",
            "content_hash": "kbs-conflict-hash",
            "cash_amount": 900,
        }
    )
    vci_revised = _cash_event(content_hash="vci-third-hash", cash_amount=1_100)

    sync_corporate_actions(conn, symbol="SSI", client=FakeCorporateActionClient([vci]))
    sync_corporate_actions(
        conn, symbol="SSI", client=FakeCorporateActionClient([kbs], provider="KBS")
    )
    result = sync_corporate_actions(
        conn, symbol="SSI", client=FakeCorporateActionClient([vci_revised])
    )

    assert result["status"] == "PARTIAL"
    assert result["revised"] == 1
    assert result["conflicts"] == 1
    rows = conn.execute(
        "SELECT cash_amount, canonical_status FROM corporate_action ORDER BY revision_number"
    ).fetchall()
    assert rows == [
        (1_000.0, "SUPERSEDED"),
        (900.0, "CONFLICT"),
        (1_100.0, "CONFLICT"),
    ]


def test_equivalent_cross_provider_terms_share_revision(conn) -> None:
    vci = _cash_event(cash_amount=1_000)
    kbs = deepcopy(vci)
    kbs.update(
        {
            "provider_event_id": "kbs-equivalent",
            "provider": "KBS",
            "source_reference": "kbs://company/SSI/events/kbs-equivalent",
            "content_hash": "kbs-equivalent-hash",
            "announced_at": "2024-01-03",
            "title": "Dividend payment from KBS feed",
        }
    )

    sync_corporate_actions(conn, symbol="SSI", client=FakeCorporateActionClient([vci]))
    result = sync_corporate_actions(
        conn, symbol="SSI", client=FakeCorporateActionClient([kbs], provider="KBS")
    )

    assert result["unchanged"] == 1
    assert result["conflicts"] == 0
    assert conn.execute("SELECT COUNT(*) FROM corporate_action").fetchone()[0] == 1
    assert (
        conn.execute("SELECT COUNT(*) FROM corporate_action_source_link").fetchone()[0]
        == 2
    )


@pytest.mark.parametrize(
    ("mutation", "expected_rule"),
    [
        ({"action_type": "OTHER"}, "UNSUPPORTED_ACTION_TYPE"),
        ({"cash_amount": None}, "INVALID_CASH_AMOUNT"),
        (
            {
                "ex_date": None,
                "record_date": None,
                "effective_date": None,
                "announced_at": None,
            },
            "MISSING_ACTION_DATE",
        ),
    ],
)
def test_malformed_evidence_is_quarantined(conn, mutation, expected_rule) -> None:
    event = _cash_event()
    event.update(mutation)
    event["content_hash"] = f"hash-{expected_rule}"

    result = sync_corporate_actions(
        conn, symbol="SSI", client=FakeCorporateActionClient([event])
    )

    assert result["status"] == "PARTIAL"
    assert result["quarantined"] == 1
    assert conn.execute("SELECT COUNT(*) FROM corporate_action").fetchone()[0] == 0
    rules = conn.execute(
        "SELECT rule_ids_json FROM corporate_action_quarantine"
    ).fetchone()[0]
    assert expected_rule in rules


def test_unknown_symbol_identity_is_quarantined(conn) -> None:
    event = _cash_event()
    event["symbol"] = "UNKNOWN"
    event["content_hash"] = "unknown-hash"

    result = sync_corporate_actions(
        conn, symbol="UNKNOWN", client=FakeCorporateActionClient([event])
    )

    assert result["quarantined"] == 1
    assert (
        "UNKNOWN_SYMBOL_IDENTITY"
        in conn.execute(
            "SELECT rule_ids_json FROM corporate_action_quarantine"
        ).fetchone()[0]
    )


def test_valid_empty_sync_is_truthful_success(conn) -> None:
    result = sync_corporate_actions(
        conn, symbol="SSI", client=FakeCorporateActionClient([])
    )
    assert result["status"] == "EMPTY"
    assert result["observed"] == 0
    assert result["canonical_inserted"] == 0


def test_unsupported_and_failed_provider_results_are_typed(conn) -> None:
    unsupported = sync_corporate_actions(
        conn,
        symbol="SSI",
        client=FailingCorporateActionClient(
            status_code=404, body='{"error":"unsupported_dataset"}'
        ),
    )
    failed = sync_corporate_actions(
        conn,
        symbol="SSI",
        client=FailingCorporateActionClient(
            status_code=502, body='{"error":"provider_fetch_error"}'
        ),
    )

    assert unsupported["status"] == "UNSUPPORTED"
    assert failed["status"] == "FAILED"
    rows = conn.execute(
        """
        SELECT status, requested_count, failed_count, terminal_reason
        FROM ingestion_run
        WHERE source_endpoint='/v1/reference/corporate-actions'
        ORDER BY started_at
        """
    ).fetchall()
    assert rows == [
        ("UNSUPPORTED", 1, 1, "UNSUPPORTED"),
        ("FAILED", 1, 1, "FAILED"),
    ]


def test_status_reports_canonical_quarantine_and_affected_ranges(conn) -> None:
    sync_corporate_actions(
        conn, symbol="SSI", client=FakeCorporateActionClient([_cash_event()])
    )
    status = corporate_action_status(conn, symbol="SSI")
    assert status["canonical_status_counts"] == {"ACTIVE": 1}
    assert status["quarantined"] == 0
    assert status["unresolved_affected_ranges"] == 1
    assert status["latest_run"]["status"] == "COMPLETE"
