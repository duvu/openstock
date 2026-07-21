from __future__ import annotations

from collections.abc import Generator
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from vnalpha.research_intelligence.models import MarketRegimeSnapshot
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import get_market_regime_as_of, upsert_symbol

TARGET_DATE = date(2024, 6, 28)
GENERATED_AT = datetime(2024, 6, 29, tzinfo=timezone.utc)
GOLDEN_FIXTURE = Path(__file__).parent / "fixtures" / "market_regime_golden.json"
PROHIBITED_TERMS = (
    "allocation",
    "portfolio",
    "buy",
    "sell",
    "order",
    "broker",
    "margin",
    "trade",
    "trading",
    "execution",
    "recommendation",
)


@pytest.fixture
def conn() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _insert_benchmark(
    conn: duckdb.DuckDBPyConnection,
    closes: list[float],
) -> None:
    dates = pd.date_range(end=TARGET_DATE, periods=len(closes), freq="B")
    rows = [
        (
            "VNINDEX",
            timestamp.date(),
            "1D",
            close,
            close,
            close,
            close,
            1_000_000.0,
            "test",
            "PASS",
            "benchmark-run",
            "service-run",
        )
        for timestamp, close in zip(dates, closes, strict=True)
    ]
    conn.executemany(
        """
        INSERT INTO canonical_ohlcv (
            symbol, time, interval, open, high, low, close, volume,
            selected_provider, quality_status, ingestion_run_id, source_service_run_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def _insert_feature(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    *,
    above_ma20: bool,
    above_ma50: bool,
    positive_return: bool,
    exact: bool = True,
) -> None:
    upsert_symbol(conn, symbol)
    as_of_bar_date = TARGET_DATE if exact else date(2024, 6, 27)
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, close, ma20, ma50, return_20d, as_of_bar_date,
            feature_data_status, source_row_count, feature_build_version,
            feature_generated_at, lineage_json, feature_profile,
            neutral_completeness
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'MINIMAL_20', 'COMPLETE')
        """,
        [
            symbol,
            TARGET_DATE,
            101.0 if above_ma20 else 99.0,
            100.0,
            100.0 if above_ma50 else 102.0,
            0.01 if positive_return else -0.01,
            as_of_bar_date,
            "EXACT_DATE" if exact else "STALE_DATE",
            70,
            "test",
            GENERATED_AT,
            '{"fixture":"feature"}',
        ],
    )


def _insert_breadth(
    conn: duckdb.DuckDBPyConnection,
    *,
    count: int = 5,
    ma20_count: int = 5,
    ma50_count: int = 5,
    positive_count: int = 5,
    stale_symbols: int = 0,
) -> None:
    for number in range(count):
        _insert_feature(
            conn,
            f"SYM{number:02d}",
            above_ma20=number < ma20_count,
            above_ma50=number < ma50_count,
            positive_return=number < positive_count,
        )
    for number in range(stale_symbols):
        _insert_feature(
            conn,
            f"STALE{number:02d}",
            above_ma20=True,
            above_ma50=True,
            positive_return=True,
            exact=False,
        )


def _build(
    conn: duckdb.DuckDBPyConnection,
) -> MarketRegimeSnapshot:
    from vnalpha.research_intelligence.policy import LEGACY_MARKET_REGIME_POLICY
    from vnalpha.research_intelligence.regime import build_market_regime

    return build_market_regime(
        conn,
        TARGET_DATE,
        generated_at=GENERATED_AT,
        policy=LEGACY_MARKET_REGIME_POLICY,
    )


def test_build_market_regime_persists_deterministic_risk_on_snapshot(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: an upward benchmark and broad exact-date participation.
    _insert_benchmark(conn, [100.0 + number for number in range(70)])
    _insert_breadth(conn)

    # When: the same dated context is built twice with a fixed timestamp.
    first = _build(conn)
    second = _build(conn)

    # Then: the persisted, complete snapshot is deterministic and risk-on.
    assert first == second
    assert first.regime == "RISK_ON"
    assert first.trend == "UPTREND"
    assert first.volatility == "NORMAL"
    assert first.pct_above_ma20 == pytest.approx(1.0)
    assert first.pct_above_ma50 == pytest.approx(1.0)
    assert first.methodology_version == "market-regime-v1"
    assert first.lineage["benchmark_freshness"] == "EXACT_DATE"
    assert get_market_regime_as_of(conn, TARGET_DATE) == first
