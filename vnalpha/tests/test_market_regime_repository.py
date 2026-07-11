from __future__ import annotations

from collections.abc import Generator
from dataclasses import replace
from datetime import date, datetime, timezone

import duckdb
import pytest

from vnalpha.research_intelligence.models import (
    MarketRegimeSnapshot,
    SectorStrengthSnapshot,
)
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    get_latest_market_regime,
    get_latest_sector_strength,
    get_market_regime_as_of,
    get_sector_strength_as_of,
    get_symbol_sector_alignment,
    replace_sector_strength_snapshots,
    upsert_market_regime_snapshot,
    upsert_sector_strength_snapshots,
    upsert_symbol,
)


@pytest.fixture
def conn() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _regime_snapshot(
    as_of_date: date, *, close: float = 1300.0
) -> MarketRegimeSnapshot:
    return MarketRegimeSnapshot(
        as_of_date=as_of_date,
        benchmark_symbol="VNINDEX",
        benchmark_bar_date=as_of_date,
        close=close,
        ma20=1280.0,
        ma50=1250.0,
        ma50_slope=0.02,
        return20=0.04,
        return60=0.12,
        volatility20=0.18,
        breadth_active_count=100,
        breadth_eligible_count=95,
        breadth_excluded_count=5,
        breadth_coverage=0.95,
        pct_above_ma20=0.62,
        pct_above_ma50=0.58,
        pct_positive_return20=0.55,
        regime="RISK_ON",
        trend="UPTREND",
        volatility="NORMAL",
        quality="COMPLETE",
        caveats=("Coverage excludes inactive symbols.",),
        lineage={"source": "canonical_ohlcv"},
        methodology_version="v1",
        generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


def _sector_snapshot(
    as_of_date: date, sector: str, rank: int
) -> SectorStrengthSnapshot:
    return SectorStrengthSnapshot(
        as_of_date=as_of_date,
        sector=sector,
        rank=rank,
        member_count=10,
        eligible_count=9,
        median_return20=0.04,
        median_return60=0.10,
        median_rs20_vs_vnindex=0.01,
        median_rs60_vs_vnindex=0.03,
        pct_above_ma20=0.66,
        pct_above_ma50=0.55,
        leadership_count=7,
        score=0.82,
        rotation="IMPROVING",
        metadata_coverage=0.90,
        unclassified_count=1,
        quality="COMPLETE",
        caveats=(),
        lineage={"source": "feature_snapshot"},
        methodology_version="v1",
        generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


def test_migrations_create_market_regime_and_sector_strength_tables(conn) -> None:
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}

    assert {"market_regime_snapshot", "sector_strength_snapshot"} <= tables


def test_migrations_normalize_legacy_leadership_count_to_integer() -> None:
    legacy_connection = in_memory_connection()
    try:
        legacy_connection.execute(
            """
            CREATE TABLE sector_strength_snapshot (
                as_of_date DATE NOT NULL,
                sector VARCHAR NOT NULL,
                rank INTEGER NOT NULL,
                member_count INTEGER NOT NULL,
                eligible_count INTEGER NOT NULL,
                median_return20 DOUBLE NOT NULL,
                median_return60 DOUBLE NOT NULL,
                median_rs20_vs_vnindex DOUBLE NOT NULL,
                median_rs60_vs_vnindex DOUBLE NOT NULL,
                pct_above_ma20 DOUBLE NOT NULL,
                pct_above_ma50 DOUBLE NOT NULL,
                leadership_count VARCHAR,
                score DOUBLE NOT NULL,
                rotation VARCHAR NOT NULL,
                metadata_coverage DOUBLE NOT NULL,
                unclassified_count INTEGER NOT NULL,
                quality VARCHAR NOT NULL,
                caveats_json VARCHAR NOT NULL,
                lineage_json VARCHAR NOT NULL,
                methodology_version VARCHAR NOT NULL,
                generated_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (as_of_date, sector)
            )
            """
        )
        legacy_connection.execute(
            """
            INSERT INTO sector_strength_snapshot VALUES
                ('2020-01-01', 'Valid', 1, 1, 1, 0, 0, 0, 0, 0, 0, '7', 0, 'NONE', 0, 0, 'COMPLETE', '[]', '{}', 'v0', current_timestamp),
                ('2020-01-01', 'Invalid', 2, 1, 1, 0, 0, 0, 0, 0, 0, '7.5', 0, 'NONE', 0, 0, 'COMPLETE', '[]', '{}', 'v0', current_timestamp),
                ('2020-01-01', 'Null', 3, 1, 1, 0, 0, 0, 0, 0, 0, NULL, 0, 'NONE', 0, 0, 'COMPLETE', '[]', '{}', 'v0', current_timestamp)
            """
        )

        run_migrations(conn=legacy_connection)
        columns = {
            row[0]: row[1]
            for row in legacy_connection.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'sector_strength_snapshot'
                """
            ).fetchall()
        }
        legacy_values = legacy_connection.execute(
            """
            SELECT sector, leadership_count
            FROM sector_strength_snapshot
            WHERE as_of_date = '2020-01-01'
            ORDER BY sector
            """
        ).fetchall()
        legacy_snapshots = get_sector_strength_as_of(
            legacy_connection, date(2020, 1, 1)
        )
        snapshot = _sector_snapshot(date(2026, 7, 1), "Technology", 1)

        upsert_sector_strength_snapshots(legacy_connection, (snapshot,))

        assert columns["leadership_count"] == "INTEGER"
        assert legacy_values == [("Invalid", None), ("Null", None), ("Valid", 7)]
        assert [legacy_snapshot.sector for legacy_snapshot in legacy_snapshots] == [
            "Valid"
        ]
        assert [
            legacy_snapshot.leadership_count for legacy_snapshot in legacy_snapshots
        ] == [7]
        assert get_sector_strength_as_of(legacy_connection, date(2026, 7, 1)) == [
            snapshot
        ]
    finally:
        legacy_connection.close()


def test_regime_upsert_and_as_of_read_deserializes_typed_fields(conn) -> None:
    snapshot = _regime_snapshot(date(2026, 7, 1))

    upsert_market_regime_snapshot(conn, snapshot)
    persisted = get_market_regime_as_of(conn, "2026-07-01")

    assert persisted == snapshot


def test_regime_round_trip_preserves_unavailable_return_context(conn) -> None:
    # Given: a valid snapshot whose optional return windows are unavailable.
    snapshot = replace(_regime_snapshot(date(2026, 7, 1)), return20=None, return60=None)

    # When: the snapshot is persisted and read by its date.
    upsert_market_regime_snapshot(conn, snapshot)
    persisted = get_market_regime_as_of(conn, date(2026, 7, 1))

    # Then: null return windows round-trip without fabricated numeric values.
    assert persisted == snapshot


def test_migrations_upgrade_legacy_breadth_columns_truthfully() -> None:
    # Given: a legacy market context row with its historical active and usable counts.
    legacy_connection = in_memory_connection()
    legacy_connection.execute(
        """
        CREATE TABLE market_regime_snapshot (
            as_of_date DATE PRIMARY KEY, benchmark_symbol VARCHAR NOT NULL,
            benchmark_bar_date DATE NOT NULL, close DOUBLE NOT NULL, ma20 DOUBLE NOT NULL,
            ma50 DOUBLE NOT NULL, ma50_slope DOUBLE NOT NULL, return20 DOUBLE NOT NULL,
            return60 DOUBLE NOT NULL, volatility20 DOUBLE NOT NULL,
            breadth_eligible_count INTEGER NOT NULL, breadth_feature_count INTEGER NOT NULL,
            pct_above_ma20 DOUBLE, pct_above_ma50 DOUBLE, pct_positive_return20 DOUBLE,
            regime VARCHAR NOT NULL, trend VARCHAR NOT NULL, volatility VARCHAR NOT NULL,
            quality VARCHAR NOT NULL, caveats_json VARCHAR NOT NULL, lineage_json VARCHAR NOT NULL,
            methodology_version VARCHAR NOT NULL, generated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    legacy_connection.execute(
        """
        INSERT INTO market_regime_snapshot VALUES (
            '2026-07-01', 'VNINDEX', '2026-07-01', 1300, 1280, 1250, 0.02,
            0.04, 0.12, 0.18, 100, 95, 0.62, 0.58, 0.55, 'RISK_ON',
            'UPTREND', 'NORMAL', 'COMPLETE', '[]', '{}', 'v1', current_timestamp
        ), (
            '2026-07-02', 'VNINDEX', '2026-07-02', 1300, 1280, 1250, 0.02,
            0.04, 0.12, 0.18, 0, 0, NULL, NULL, NULL, 'INSUFFICIENT_DATA',
            'INSUFFICIENT_DATA', 'INSUFFICIENT_DATA', 'INCOMPLETE', '[]', '{}', 'v1', current_timestamp
        )
        """
    )

    # When: the additive warehouse migration runs.
    run_migrations(conn=legacy_connection)

    # Then: explicit breadth columns truthfully retain the legacy semantics.
    row = legacy_connection.execute(
        """
        SELECT breadth_active_count, breadth_eligible_count, breadth_excluded_count,
               breadth_coverage
        FROM market_regime_snapshot
        """
    ).fetchone()
    assert row == pytest.approx((100, 95, 5, 0.95))
    assert get_market_regime_as_of(legacy_connection, date(2026, 7, 2)) is None
    legacy_connection.close()


def test_migrations_adds_missing_return_columns_for_partial_legacy_schema() -> None:
    # Given: a legacy market context table without either optional return column.
    legacy_connection = in_memory_connection()
    legacy_connection.execute(
        """
        CREATE TABLE market_regime_snapshot (
            as_of_date DATE PRIMARY KEY, benchmark_symbol VARCHAR NOT NULL,
            benchmark_bar_date DATE NOT NULL, close DOUBLE NOT NULL, ma20 DOUBLE NOT NULL,
            ma50 DOUBLE NOT NULL, ma50_slope DOUBLE NOT NULL, volatility20 DOUBLE NOT NULL,
            breadth_eligible_count INTEGER NOT NULL, breadth_feature_count INTEGER NOT NULL,
            pct_above_ma20 DOUBLE, pct_above_ma50 DOUBLE, pct_positive_return20 DOUBLE,
            regime VARCHAR NOT NULL, trend VARCHAR NOT NULL, volatility VARCHAR NOT NULL,
            quality VARCHAR NOT NULL, caveats_json VARCHAR NOT NULL, lineage_json VARCHAR NOT NULL,
            methodology_version VARCHAR NOT NULL, generated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    legacy_connection.execute(
        """
        INSERT INTO market_regime_snapshot VALUES (
            '2026-07-01', 'VNINDEX', '2026-07-01', 1300, 1280, 1250, 0.02,
            0.18, 100, 95, 0.62, 0.58, 0.55, 'RISK_ON', 'UPTREND', 'NORMAL',
            'COMPLETE', '[]', '{}', 'v1', current_timestamp
        )
        """
    )

    # When: migrations run repeatedly against the partial schema.
    run_migrations(conn=legacy_connection)
    run_migrations(conn=legacy_connection)

    # Then: nullable return columns exist and the derivable snapshot stays readable.
    columns = {
        row[0]
        for row in legacy_connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'market_regime_snapshot'
            """
        ).fetchall()
    }
    snapshot = get_market_regime_as_of(legacy_connection, date(2026, 7, 1))
    assert {"return20", "return60"} <= columns
    assert snapshot is not None
    assert snapshot.return20 is None
    assert snapshot.return60 is None
    legacy_connection.close()


def test_snapshot_normalizes_caller_owned_caveats_and_lineage() -> None:
    caveats = ["Initial caveat"]
    lineage = {"source": "canonical_ohlcv"}
    snapshot = replace(
        _regime_snapshot(date(2026, 7, 1)), caveats=caveats, lineage=lineage
    )

    caveats.append("Later caveat")
    lineage["source"] = "changed"

    assert snapshot.caveats == ("Initial caveat",)
    assert snapshot.lineage == {"source": "canonical_ohlcv"}
    with pytest.raises(TypeError):
        snapshot.lineage["new"] = "value"


def test_regime_read_defaults_null_and_malformed_json_to_immutable_values(conn) -> None:
    null_json_snapshot = _regime_snapshot(date(2026, 7, 1))
    malformed_json_snapshot = _regime_snapshot(date(2026, 7, 2))
    upsert_market_regime_snapshot(conn, null_json_snapshot)
    upsert_market_regime_snapshot(conn, malformed_json_snapshot)
    conn.execute(
        "ALTER TABLE market_regime_snapshot ALTER COLUMN caveats_json DROP NOT NULL"
    )
    conn.execute(
        "ALTER TABLE market_regime_snapshot ALTER COLUMN lineage_json DROP NOT NULL"
    )
    conn.execute(
        """
        UPDATE market_regime_snapshot
        SET caveats_json = NULL, lineage_json = NULL
        WHERE as_of_date = '2026-07-01'
        """
    )
    conn.execute(
        """
        UPDATE market_regime_snapshot
        SET caveats_json = '{', lineage_json = '[]'
        WHERE as_of_date = '2026-07-02'
        """
    )

    null_json = get_market_regime_as_of(conn, date(2026, 7, 1))
    malformed_json = get_market_regime_as_of(conn, date(2026, 7, 2))

    assert null_json is not None
    assert null_json.caveats == ()
    assert null_json.lineage == {}
    assert malformed_json is not None
    assert malformed_json.caveats == ()
    assert malformed_json.lineage == {}
    with pytest.raises(TypeError):
        malformed_json.lineage["new"] = "value"


def test_regime_upsert_replaces_same_as_of_date(conn) -> None:
    upsert_market_regime_snapshot(conn, _regime_snapshot(date(2026, 7, 1)))
    upsert_market_regime_snapshot(
        conn, _regime_snapshot(date(2026, 7, 1), close=1310.0)
    )

    persisted = get_market_regime_as_of(conn, date(2026, 7, 1))

    assert persisted is not None
    assert persisted.close == pytest.approx(1310.0)


def test_latest_regime_uses_maximum_persisted_date(conn) -> None:
    upsert_market_regime_snapshot(conn, _regime_snapshot(date(2026, 6, 30)))
    expected = _regime_snapshot(date(2026, 7, 1))
    upsert_market_regime_snapshot(conn, expected)

    assert get_latest_market_regime(conn) == expected


def test_absent_regime_reads_return_none(conn) -> None:
    assert get_market_regime_as_of(conn, date(2026, 7, 1)) is None
    assert get_latest_market_regime(conn) is None


def test_sector_bulk_upsert_lists_exact_snapshots_by_rank_then_sector(conn) -> None:
    as_of_date = date(2026, 7, 1)
    finance = _sector_snapshot(as_of_date, "Financials", 1)
    technology = _sector_snapshot(as_of_date, "Technology", 1)
    industrials = _sector_snapshot(as_of_date, "Industrials", 2)

    upsert_sector_strength_snapshots(conn, (industrials, technology, finance))

    assert get_sector_strength_as_of(conn, as_of_date) == [
        finance,
        technology,
        industrials,
    ]


def test_sector_latest_list_uses_maximum_persisted_date(conn) -> None:
    upsert_sector_strength_snapshots(
        conn, [_sector_snapshot(date(2026, 6, 30), "Financials", 1)]
    )
    expected = _sector_snapshot(date(2026, 7, 1), "Technology", 1)
    upsert_sector_strength_snapshots(conn, [expected])

    assert get_latest_sector_strength(conn) == [expected]


def test_absent_sector_snapshots_return_empty_list(conn) -> None:
    assert get_sector_strength_as_of(conn, date(2026, 7, 1)) == []
    assert get_latest_sector_strength(conn) == []


def test_sector_bulk_upsert_replaces_conflicting_snapshot(conn) -> None:
    snapshot = _sector_snapshot(date(2026, 7, 1), "Technology", 1)
    replacement = replace(snapshot, leadership_count=8, score=0.91)

    upsert_sector_strength_snapshots(conn, (snapshot,))
    upsert_sector_strength_snapshots(conn, (replacement,))

    assert get_sector_strength_as_of(conn, date(2026, 7, 1)) == [replacement]


def test_owned_sector_replacement_rolls_back_deleted_rows_when_an_upsert_fails(
    conn,
) -> None:
    # Given: a persisted snapshot and a database uniqueness rule for replacement rows.
    as_of_date = date(2026, 7, 1)
    original = _sector_snapshot(as_of_date, "Original", 1)
    financials = replace(original, sector="Financials", score=0.91)
    technology = replace(original, sector="Technology", score=0.91)
    upsert_sector_strength_snapshots(conn, (original,))
    conn.execute(
        "CREATE UNIQUE INDEX sector_strength_unique_score "
        "ON sector_strength_snapshot (as_of_date, score)"
    )

    # When: an owned replacement deletes then encounters an actual database failure.
    with pytest.raises(duckdb.ConstraintException):
        replace_sector_strength_snapshots(conn, as_of_date, (financials, technology))

    # Then: rollback restores the prior row and leaves the connection usable.
    assert get_sector_strength_as_of(conn, as_of_date) == [original]
    assert conn.execute("SELECT 1").fetchone() == (1,)


def test_caller_owned_sector_replacement_does_not_control_outer_transaction(
    conn,
) -> None:
    # Given: an outer transaction and a persisted sector snapshot.
    as_of_date = date(2026, 7, 1)
    original = _sector_snapshot(as_of_date, "Original", 1)
    replacement = replace(original, sector="Technology", score=0.91)
    upsert_sector_strength_snapshots(conn, (original,))
    conn.execute("BEGIN TRANSACTION")

    # When: replacement is explicitly delegated to the caller-owned transaction.
    replace_sector_strength_snapshots(
        conn, as_of_date, (replacement,), owns_transaction=False
    )
    conn.execute("ROLLBACK")

    # Then: no nested transaction occurs and the caller controls rollback.
    assert get_sector_strength_as_of(conn, as_of_date) == [original]


def test_sector_replacement_rejects_mismatched_dates_before_mutating_date_scope(
    conn,
) -> None:
    # Given: a Date A snapshot and a replacement snapshot belonging to Date B.
    date_a = date(2026, 7, 1)
    original = _sector_snapshot(date_a, "Original", 1)
    mismatched = _sector_snapshot(date(2026, 7, 2), "Technology", 1)
    upsert_sector_strength_snapshots(conn, (original,))

    # When: caller-owned replacement receives the mismatched Date B input.
    with pytest.raises(ValueError, match="does not match replacement date"):
        replace_sector_strength_snapshots(
            conn, date_a, (mismatched,), owns_transaction=False
        )

    # Then: validation prevents mutation of Date A without transaction control.
    assert get_sector_strength_as_of(conn, date_a) == [original]


def test_owned_sector_replacement_prepares_json_before_deleting_rows(conn) -> None:
    # Given: a persisted snapshot and a runtime-invalid lineage in its replacement.
    as_of_date = date(2026, 7, 1)
    original = _sector_snapshot(as_of_date, "Original", 1)
    invalid = replace(original, sector="Technology")
    object.__setattr__(invalid, "lineage", {"nonserializable": {"value"}})
    upsert_sector_strength_snapshots(conn, (original,))

    # When: owned replacement encounters JSON serialization failure.
    with pytest.raises(TypeError, match="not JSON serializable"):
        replace_sector_strength_snapshots(conn, as_of_date, (invalid,))

    # Then: Date A remains persisted and the connection remains usable.
    assert get_sector_strength_as_of(conn, as_of_date) == [original]
    assert conn.execute("SELECT 1").fetchone() == (1,)


def test_sector_strength_as_of_applies_limit_after_deterministic_order(conn) -> None:
    as_of_date = date(2026, 7, 1)
    finance = _sector_snapshot(as_of_date, "Financials", 1)
    technology = _sector_snapshot(as_of_date, "Technology", 1)
    industrials = _sector_snapshot(as_of_date, "Industrials", 2)
    upsert_sector_strength_snapshots(conn, (industrials, technology, finance))

    assert get_sector_strength_as_of(conn, as_of_date, limit=2) == [finance, technology]


def test_latest_sector_strength_applies_limit_after_deterministic_order(conn) -> None:
    as_of_date = date(2026, 7, 1)
    finance = _sector_snapshot(as_of_date, "Financials", 1)
    technology = _sector_snapshot(as_of_date, "Technology", 1)
    upsert_sector_strength_snapshots(conn, (technology, finance))

    assert get_latest_sector_strength(conn, limit=1) == [finance]


def test_symbol_alignment_uses_persisted_sector_and_exact_snapshot(conn) -> None:
    snapshot = _sector_snapshot(date(2026, 7, 1), "Technology", 1)
    upsert_symbol(conn, "FPT", sector="Technology")
    upsert_sector_strength_snapshots(conn, [snapshot])

    alignment = get_symbol_sector_alignment(conn, "FPT", date(2026, 7, 1))

    assert alignment is not None
    assert alignment.symbol == "FPT"
    assert alignment.sector == "Technology"
    assert alignment.snapshot == snapshot


def test_symbol_alignment_preserves_missing_sector_metadata(conn) -> None:
    upsert_symbol(conn, "VNM")

    alignment = get_symbol_sector_alignment(conn, "VNM")

    assert alignment is not None
    assert alignment.sector is None
    assert alignment.snapshot is None


def test_symbol_alignment_returns_none_snapshot_when_sector_snapshot_is_absent(
    conn,
) -> None:
    upsert_symbol(conn, "FPT", sector="Technology")

    alignment = get_symbol_sector_alignment(conn, "FPT", date(2026, 7, 1))

    assert alignment is not None
    assert alignment.sector == "Technology"
    assert alignment.snapshot is None


def test_symbol_alignment_without_date_uses_latest_persisted_sector_snapshot(
    conn,
) -> None:
    current = _sector_snapshot(date(2026, 7, 1), "Technology", 1)
    latest = replace(current, as_of_date=date(2026, 7, 2), score=0.91)
    upsert_symbol(conn, "FPT", sector="Technology")
    upsert_sector_strength_snapshots(conn, (current, latest))

    alignment = get_symbol_sector_alignment(conn, "FPT")

    assert alignment is not None
    assert alignment.snapshot == latest
