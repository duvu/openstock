"""Regression coverage for validation-first canonical OHLCV promotion."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from vnalpha.features.build_features import build_features, load_canonical_ohlcv
from vnalpha.ingestion.build_canonical import build_canonical_ohlcv
from vnalpha.ingestion.canonical_validation import CanonicalCandidate
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import create_ingestion_run


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    """Provide a migrated in-memory warehouse."""

    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _insert_raw_bar(
    conn: duckdb.DuckDBPyConnection,
    *,
    symbol: str,
    close: float,
    open: float = 10.0,
    high: float = 11.0,
    low: float = 9.0,
    volume: float = 1_000.0,
    provider: str = "fixture",
    quality_status: str = "pass",
    fetched_at: str = "2026-01-06 00:00:00",
    timestamp: str = "2026-01-05",
) -> str:
    """Insert one deterministic raw observation for canonical promotion."""

    run_id = create_ingestion_run(conn, "fixture", "/ohlcv")
    conn.execute(
        """
        INSERT INTO market_ohlcv_raw
            (ingestion_run_id, symbol, time, interval, open, high, low, close,
             volume, provider, quality_status, fetched_at)
        VALUES (?, ?, ?, '1D', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            symbol,
            timestamp,
            open,
            high,
            low,
            close,
            volume,
            provider,
            quality_status,
            fetched_at,
        ],
    )
    return run_id


def test_invalid_close_is_quarantined_before_canonical_promotion(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """A non-positive close is rejected instead of becoming canonical data."""

    _insert_raw_bar(conn, symbol="BAD", close=0.0)

    result = build_canonical_ohlcv(conn, symbol="BAD")

    canonical_count = conn.execute(
        "SELECT COUNT(*) FROM canonical_ohlcv WHERE symbol = 'BAD'"
    ).fetchone()
    rejection_count = conn.execute(
        "SELECT COUNT(*) FROM rejected_symbol WHERE symbol = 'BAD'"
    ).fetchone()
    assert canonical_count == (0,)
    assert rejection_count == (1,)
    assert result["upserted"] == 0
    assert result["rejected"] == 1


def test_migrations_create_provider_and_run_keyed_quarantine_table(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Quarantine evidence has a key for each raw provider observation."""

    columns = {
        row[0]
        for row in conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = 'ohlcv_quarantine'
            """
        ).fetchall()
    }

    assert {
        "ingestion_run_id",
        "symbol",
        "time",
        "interval",
        "provider",
        "rule_ids_json",
        "validation_version",
        "first_detected_at",
        "last_detected_at",
        "resolution_ref",
    } <= columns


def test_invalid_observation_persists_idempotent_quarantine_lineage(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Repeated validation retains one provider/run-keyed quarantine record."""

    run_id = _insert_raw_bar(conn, symbol="BAD", close=0.0)

    build_canonical_ohlcv(conn, symbol="BAD")
    build_canonical_ohlcv(conn, symbol="BAD")

    row = conn.execute(
        """
        SELECT
            provider, ingestion_run_id, rule_ids_json, validation_version,
            invalid_values_json, first_detected_at, last_detected_at,
            resolution_ref
        FROM ohlcv_quarantine
        WHERE symbol = 'BAD'
        """
    ).fetchone()
    row_count = conn.execute(
        "SELECT COUNT(*) FROM ohlcv_quarantine WHERE symbol = 'BAD'"
    ).fetchone()

    assert row is not None
    assert row[0] == "fixture"
    assert row[1] == run_id
    assert "close_positive" in json.loads(row[2])
    assert row[3] == "canonical_ohlcv_v1"
    assert json.loads(row[4])["close"] == 0.0
    assert row[5] <= row[6]
    assert row[7] is None
    assert row_count == (1,)


def test_valid_replacement_restores_canonical_bar_and_resolves_quarantine(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """A higher-ranked valid observation replaces a quarantined raw bar."""

    _insert_raw_bar(
        conn,
        symbol="FPT",
        close=0.0,
        provider="first",
        fetched_at="2026-01-06 00:00:00",
    )
    build_canonical_ohlcv(conn, symbol="FPT")
    valid_run_id = _insert_raw_bar(
        conn,
        symbol="FPT",
        close=12.0,
        high=13.0,
        provider="replacement",
        fetched_at="2026-01-07 00:00:00",
    )

    result = build_canonical_ohlcv(conn, symbol="FPT")

    canonical = conn.execute(
        """
        SELECT close, selected_provider, ingestion_run_id
        FROM canonical_ohlcv
        WHERE symbol = 'FPT'
        """
    ).fetchone()
    quarantine = conn.execute(
        """
        SELECT resolution_ref
        FROM ohlcv_quarantine
        WHERE symbol = 'FPT' AND provider = 'first'
        """
    ).fetchone()
    assert result == {"upserted": 1, "rejected": 0}
    assert canonical == (12.0, "replacement", valid_run_id)
    assert quarantine == (f"canonical:{valid_run_id}:replacement",)


def test_invalid_selected_candidate_does_not_fall_back_to_lower_ranked_raw_row(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """An invalid selected observation fails closed instead of being bypassed."""

    _insert_raw_bar(
        conn,
        symbol="FPT",
        close=12.0,
        high=13.0,
        provider="fallback",
        fetched_at="2026-01-06 00:00:00",
    )
    _insert_raw_bar(
        conn,
        symbol="FPT",
        close=0.0,
        provider="selected-invalid",
        fetched_at="2026-01-07 00:00:00",
    )

    result = build_canonical_ohlcv(conn, symbol="FPT")

    canonical_count = conn.execute(
        "SELECT COUNT(*) FROM canonical_ohlcv WHERE symbol = 'FPT'"
    ).fetchone()
    quarantined_provider = conn.execute(
        "SELECT provider FROM ohlcv_quarantine WHERE symbol = 'FPT'"
    ).fetchone()
    assert result == {"upserted": 0, "rejected": 1}
    assert canonical_count == (0,)
    assert quarantined_provider == ("selected-invalid",)


def test_candidate_selection_normalizes_pass_quality_status(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Provider quality selection treats uppercase PASS as a passing candidate."""

    _insert_raw_bar(
        conn,
        symbol="FPT",
        close=12.0,
        high=13.0,
        provider="passing",
        quality_status="PASS",
        fetched_at="2026-01-06 00:00:00",
    )
    _insert_raw_bar(
        conn,
        symbol="FPT",
        close=13.0,
        high=14.0,
        provider="nonpassing",
        quality_status="fail",
        fetched_at="2026-01-07 00:00:00",
    )

    build_canonical_ohlcv(conn, symbol="FPT")

    assert conn.execute(
        "SELECT selected_provider FROM canonical_ohlcv WHERE symbol = 'FPT'"
    ).fetchone() == ("passing",)


def test_conflicting_passing_provider_observations_are_quarantined(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Conflicting passing providers cannot silently produce canonical data."""

    _insert_raw_bar(
        conn,
        symbol="FPT",
        close=12.0,
        high=13.0,
        provider="first-provider",
        fetched_at="2026-01-06 00:00:00",
    )
    _insert_raw_bar(
        conn,
        symbol="FPT",
        close=13.0,
        high=14.0,
        provider="conflicting-provider",
        fetched_at="2026-01-07 00:00:00",
    )

    result = build_canonical_ohlcv(conn, symbol="FPT")

    assert result == {"upserted": 0, "rejected": 1}
    assert conn.execute(
        "SELECT COUNT(*) FROM canonical_ohlcv WHERE symbol = 'FPT'"
    ).fetchone() == (0,)
    rules = conn.execute(
        "SELECT rule_ids_json FROM ohlcv_quarantine WHERE symbol = 'FPT'"
    ).fetchone()
    assert rules is not None
    assert json.loads(rules[0]) == ["provider_consistency"]


def test_features_receive_only_validated_canonical_history(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Quarantined raw bars cannot become inputs to feature construction."""

    start = date(2026, 1, 1)
    for day_offset in range(20):
        close = 10.0 + day_offset
        _insert_raw_bar(
            conn,
            symbol="FPT",
            close=close,
            open=close,
            high=close + 1.0,
            low=close - 1.0,
            timestamp=(start + timedelta(days=day_offset)).isoformat(),
            fetched_at=f"2026-02-{day_offset + 1:02d} 00:00:00",
        )
    _insert_raw_bar(
        conn,
        symbol="FPT",
        close=0.0,
        timestamp="2026-01-21",
        fetched_at="2026-02-21 00:00:00",
    )

    build_canonical_ohlcv(conn, symbol="FPT")
    history = load_canonical_ohlcv(conn, "FPT", "2026-01-21")
    result = build_features(conn, "2026-01-21", universe=["FPT"])

    assert len(history) == 20
    assert (history["close"] > 0).all()
    assert result == {"built": 1, "skipped": 0}


def test_canonical_build_emits_correlated_start_and_terminal_audit_events(
    conn: duckdb.DuckDBPyConnection,
    tmp_path: Path,
) -> None:
    """Canonical promotion records its full lifecycle under one correlation."""

    from vnalpha.observability.context import (
        init_run_context,
        reset_run_context,
        set_correlation_id,
    )

    reset_run_context()
    run_context = init_run_context("test", actor="test", log_root=tmp_path)
    correlation_id = set_correlation_id()
    _insert_raw_bar(conn, symbol="BAD", close=0.0)

    try:
        build_canonical_ohlcv(conn, symbol="BAD")

        records = (
            [
                json.loads(line)
                for line in run_context.audit_path.read_text().splitlines()
                if line.strip()
            ]
            if run_context.audit_path.exists()
            else []
        )
        events = [
            record
            for record in records
            if record["event_type"].startswith("CANONICAL_OHLCV_BUILD_")
        ]
        assert [event["event_type"] for event in events] == [
            "CANONICAL_OHLCV_BUILD_STARTED",
            "CANONICAL_OHLCV_BUILD_COMPLETED",
        ]
        assert {event["correlation_id"] for event in events} == {correlation_id}
        assert events[1]["metadata"] == {
            "canonical_count": 0,
            "interval": "1D",
            "rejected_count": 1,
            "symbol": "BAD",
        }
    finally:
        reset_run_context()


def test_canonical_build_rolls_back_partial_quarantine_on_storage_failure(
    conn: duckdb.DuckDBPyConnection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later storage failure does not leave a partial quarantine record."""

    from vnalpha.ingestion import build_canonical

    _insert_raw_bar(conn, symbol="BAD", close=0.0)

    def fail_delete(
        _conn: duckdb.DuckDBPyConnection,
        _candidate: CanonicalCandidate,
    ) -> None:
        raise duckdb.Error("forced delete failure")

    monkeypatch.setattr(build_canonical, "delete_canonical_bar", fail_delete)

    with pytest.raises(duckdb.Error, match="forced delete failure"):
        build_canonical.build_canonical_ohlcv(conn, symbol="BAD")

    assert conn.execute(
        "SELECT COUNT(*) FROM rejected_symbol WHERE symbol = 'BAD'"
    ).fetchone() == (0,)
    assert conn.execute(
        "SELECT COUNT(*) FROM ohlcv_quarantine WHERE symbol = 'BAD'"
    ).fetchone() == (0,)
