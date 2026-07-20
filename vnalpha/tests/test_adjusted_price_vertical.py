from __future__ import annotations

from datetime import date
from decimal import Decimal

import duckdb

from vnalpha.corporate_actions.adjusted_prices import (
    ADJUSTED_PRICE_BASIS,
    build_adjusted_ohlcv,
    derive_and_persist_factor,
    rebuild_pending_adjusted_ranges,
)
from vnalpha.corporate_actions.adjustment_factors import (
    AdjustmentType,
    build_adjustment_factor,
    calculate_split_factor,
)
from vnalpha.warehouse.migrations import run_migrations


def _conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn, emit_observability=False)
    return conn


def _insert_action(
    conn: duckdb.DuckDBPyConnection,
    *,
    revision_id: str,
    revision_number: int,
    status: str,
    ratio: float,
) -> None:
    conn.execute(
        """
        INSERT INTO corporate_action (
            revision_id, action_id, revision_number, symbol, action_type,
            ex_date, ratio, revision_hash, canonical_status, contract_version,
            affected_from_date
        ) VALUES (?, 'split-fpt', ?, 'FPT', 'SPLIT', '2026-07-15', ?, ?, ?,
                  'corporate-actions-v1', '2026-07-01')
        """,
        [revision_id, revision_number, ratio, f"hash-{revision_id}", status],
    )


def _insert_raw_bars(conn: duckdb.DuckDBPyConnection) -> None:
    conn.executemany(
        """
        INSERT INTO canonical_ohlcv (
            symbol, time, interval, open, high, low, close, volume,
            selected_provider, price_basis, quality_status, ingestion_run_id
        ) VALUES ('FPT', ?, '1D', ?, ?, ?, ?, ?, 'VCI',
                  'RAW_UNADJUSTED', 'PASS', 'run-1')
        """,
        [
            ("2026-07-14", 100.0, 101.0, 99.0, 100.0, 1000.0),
            ("2026-07-15", 50.0, 51.0, 49.0, 50.0, 1000.0),
        ],
    )


def test_split_factor_is_a_price_multiplier() -> None:
    assert calculate_split_factor(1, 2) == Decimal("0.5")
    factor = build_adjustment_factor(
        symbol="FPT",
        action_date=date(2026, 7, 15),
        adjustment_type=AdjustmentType.SPLIT,
        params={"old_shares": 1, "new_shares": 2},
    )
    assert factor.apply_to_price(Decimal("100")) == Decimal("50.0")
    assert factor.apply_to_volume(Decimal("1000")) == Decimal("2000")
    assert factor.content_hash() == factor.content_hash()


def test_adjusted_series_is_separate_and_idempotent() -> None:
    conn = _conn()
    _insert_raw_bars(conn)
    _insert_action(
        conn,
        revision_id="rev-1",
        revision_number=1,
        status="CURRENT",
        ratio=2.0,
    )
    factor_id = derive_and_persist_factor(conn, "rev-1")
    assert factor_id.startswith("adjf_")

    first = build_adjusted_ohlcv(conn, "FPT")
    second = build_adjusted_ohlcv(conn, "FPT")
    assert first.rows_written == second.rows_written == 2

    adjusted = conn.execute(
        """
        SELECT CAST(time AS DATE), close, volume, price_basis, factor_chain_hash
        FROM adjusted_ohlcv ORDER BY time
        """
    ).fetchall()
    assert adjusted[0][1] == 50.0
    assert adjusted[0][2] == 2000.0
    assert adjusted[0][3] == ADJUSTED_PRICE_BASIS
    assert adjusted[0][4]
    assert adjusted[1][1] == 50.0
    assert adjusted[1][2] == 1000.0

    raw = conn.execute(
        "SELECT close, volume FROM canonical_ohlcv ORDER BY time"
    ).fetchall()
    assert raw == [(100.0, 1000.0), (50.0, 1000.0)]
    assert conn.execute("SELECT COUNT(*) FROM adjusted_ohlcv").fetchone()[0] == 2
    conn.close()


def test_action_revision_rebuilds_only_signalled_range() -> None:
    conn = _conn()
    _insert_raw_bars(conn)
    _insert_action(
        conn,
        revision_id="rev-1",
        revision_number=1,
        status="SUPERSEDED",
        ratio=2.0,
    )
    _insert_action(
        conn,
        revision_id="rev-2",
        revision_number=2,
        status="CURRENT",
        ratio=4.0,
    )
    conn.execute(
        """
        INSERT INTO corporate_action_affected_range (
            signal_id, action_id, revision_id, symbol,
            affected_from_date, affected_to_date, reason
        ) VALUES ('signal-1', 'split-fpt', 'rev-2', 'FPT',
                  '2026-07-14', '2026-07-14', 'revision_changed')
        """
    )

    results = rebuild_pending_adjusted_ranges(conn)
    assert len(results) == 1
    row = conn.execute(
        "SELECT close FROM adjusted_ohlcv WHERE CAST(time AS DATE) = '2026-07-14'"
    ).fetchone()
    assert row == (25.0,)
    signal = conn.execute(
        "SELECT resolved_at, resolution_ref FROM corporate_action_affected_range"
    ).fetchone()
    assert signal[0] is not None
    assert signal[1]
    conn.close()


def test_research_tables_declare_basis_lineage_columns() -> None:
    conn = _conn()
    columns = {
        table: {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = ?",
                [table],
            ).fetchall()
        }
        for table in ("feature_snapshot", "candidate_score", "daily_watchlist")
    }
    for table_columns in columns.values():
        assert {
            "price_basis",
            "adjustment_version",
            "factor_chain_hash",
        } <= table_columns
    conn.close()
