"""Tests for issue #259: official disclosures as verified symbol events."""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.disclosures import (
    DisclosureOccurrence,
    EventType,
    as_of_events,
    ingest_occurrence,
    normalize_event,
    occurrence_content_hash,
)
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection, emit_observability=False)
    yield connection
    connection.close()


def _occ(**overrides) -> DisclosureOccurrence:
    base = {
        "source_authority": "HSX",
        "source_reference": "HSX-2026-0042",
        "symbol": "FPT",
        "published_at": "2026-03-31",
        "raw_title": "FPT 2025 audited annual report",
        "raw_payload": {"kind": "annual_report", "note": "<b>untrusted</b>"},
    }
    base.update(overrides)
    return DisclosureOccurrence(**base)


def test_only_approved_sources_create_verified_events(conn) -> None:
    verified = normalize_event(
        conn,
        _occ(),
        event_type=EventType.FINANCIAL_REPORT_PUBLICATION,
        event_id="FPT-2025-ANNUAL",
    )
    assert verified.verification_status == "VERIFIED"

    quarantined = normalize_event(
        conn,
        _occ(source_authority="RANDOM_BLOG", source_reference="blog-1"),
        event_type=EventType.FINANCIAL_REPORT_PUBLICATION,
        event_id="FPT-2025-ANNUAL-BLOG",
    )
    assert quarantined.verification_status == "QUARANTINED"


def test_duplicate_occurrences_deduplicate(conn) -> None:
    id1 = ingest_occurrence(conn, _occ())
    id2 = ingest_occurrence(conn, _occ())
    assert id1 == id2
    count = conn.execute("SELECT COUNT(*) FROM disclosure_raw_occurrence").fetchone()[0]
    assert count == 1


def test_revised_disclosure_supersedes_prior(conn) -> None:
    normalize_event(
        conn,
        _occ(),
        event_type=EventType.FINANCIAL_REPORT_PUBLICATION,
        event_id="FPT-2025-ANNUAL",
    )
    normalize_event(
        conn,
        _occ(source_reference="HSX-2026-0042-R2", raw_title="restated report"),
        event_type=EventType.FINANCIAL_REPORT_PUBLICATION,
        event_id="FPT-2025-ANNUAL",
    )
    rows = conn.execute(
        "SELECT revision_number, canonical_status FROM symbol_event "
        "WHERE event_id = 'FPT-2025-ANNUAL' ORDER BY revision_number"
    ).fetchall()
    assert [r[1] for r in rows] == ["SUPERSEDED", "CURRENT"]


def test_publication_and_event_dates_stay_distinct(conn) -> None:
    normalize_event(
        conn,
        _occ(published_at="2026-03-31"),
        event_type=EventType.SHAREHOLDER_MEETING_OR_RESOLUTION,
        event_id="FPT-AGM-2026",
        event_date="2026-04-25",
    )
    row = conn.execute(
        "SELECT published_at, event_date FROM symbol_event WHERE event_id='FPT-AGM-2026'"
    ).fetchone()
    assert str(row[0]) == "2026-03-31"
    assert str(row[1]) == "2026-04-25"


def test_future_disclosures_do_not_leak_into_historical_reads(conn) -> None:
    normalize_event(
        conn,
        _occ(published_at="2026-03-31"),
        event_type=EventType.FINANCIAL_REPORT_PUBLICATION,
        event_id="FPT-2025-ANNUAL",
    )
    # As of before publication: no events.
    assert as_of_events(conn, "FPT", "2026-03-01") == []
    # As of after publication: visible.
    later = as_of_events(conn, "FPT", "2026-04-01")
    assert len(later) == 1
    assert later[0]["event_type"] == "FINANCIAL_REPORT_PUBLICATION"


def test_as_of_excludes_quarantined_by_default(conn) -> None:
    normalize_event(
        conn,
        _occ(source_authority="RANDOM_BLOG", source_reference="blog-2"),
        event_type=EventType.TRADING_STATUS_CHANGE,
        event_id="FPT-SUSPEND-RUMOR",
    )
    assert as_of_events(conn, "FPT", "2026-12-31") == []
    including = as_of_events(conn, "FPT", "2026-12-31", verified_only=False)
    assert len(including) == 1
    assert including[0]["verification_status"] == "QUARANTINED"


def test_superseded_events_do_not_reappear(conn) -> None:
    normalize_event(
        conn,
        _occ(),
        event_type=EventType.FINANCIAL_REPORT_PUBLICATION,
        event_id="FPT-2025-ANNUAL",
    )
    normalize_event(
        conn,
        _occ(source_reference="HSX-2026-0042-R2"),
        event_type=EventType.FINANCIAL_REPORT_PUBLICATION,
        event_id="FPT-2025-ANNUAL",
    )
    events = as_of_events(conn, "FPT", "2026-12-31")
    # Only the current revision surfaces.
    assert len(events) == 1


def test_content_hash_is_stable_and_sensitive() -> None:
    h1 = occurrence_content_hash(_occ())
    h2 = occurrence_content_hash(_occ())
    h3 = occurrence_content_hash(_occ(raw_title="different"))
    assert h1 == h2
    assert h1 != h3


def test_untrusted_payload_stored_verbatim_not_executed(conn) -> None:
    # The raw payload is persisted as opaque JSON text; it is never evaluated.
    ingest_occurrence(
        conn, _occ(raw_payload={"script": "__import__('os').system('x')"})
    )
    stored = conn.execute(
        "SELECT raw_payload_json FROM disclosure_raw_occurrence LIMIT 1"
    ).fetchone()[0]
    assert "__import__" in stored  # stored as data, not executed
