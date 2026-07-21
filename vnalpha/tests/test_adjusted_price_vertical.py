from __future__ import annotations

from datetime import date
from decimal import Decimal

import duckdb

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
