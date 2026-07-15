from __future__ import annotations

import json
from collections.abc import Generator
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from vnalpha.data_availability.deep_context_evidence import market_issues, sector_issues
from vnalpha.data_availability.deep_readiness_models import ContextIssue
from vnalpha.research_intelligence.regime import build_market_regime
from vnalpha.research_intelligence.sector import build_sector_strength
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import upsert_symbol

TARGET_DATE = date(2024, 6, 28)
GENERATED_AT = datetime(2024, 6, 29, tzinfo=timezone.utc)
GOLDEN = json.loads(
    (
        Path(__file__).parent / "fixtures" / "market_context_production_golden.json"
    ).read_text()
)


@pytest.fixture
def conn() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _insert_benchmark(conn: duckdb.DuckDBPyConnection, closes: list[float]) -> None:
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
            "fixture",
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


def _insert_symbol_feature(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    *,
    sector: str | None = "Technology",
    exchange: str = "HOSE",
    security_type: str = "COMMON_EQUITY",
    return20: float = 0.10,
    return60: float = 0.05,
    rs20: float = 0.03,
    rs60: float = 0.01,
    above_ma20: bool = True,
    above_ma50: bool = True,
    volume_ma20: float = 20_000.0,
    taxonomy: bool = True,
) -> None:
    upsert_symbol(conn, symbol, exchange=exchange, sector=sector)
    conn.execute(
        """
        UPDATE symbol_master
        SET security_type = ?, lifecycle_status = 'ACTIVE', sector_name = ?,
            taxonomy_name = ?, taxonomy_version = ?
        WHERE symbol = ?
        """,
        [
            security_type,
            sector,
            "ICB" if taxonomy and sector else None,
            "2024" if taxonomy and sector else None,
            symbol,
        ],
    )
    close = 101.0 if above_ma20 else 99.0
    ma50 = 100.0 if above_ma50 else 102.0
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, close, ma20, ma50, volume_ma20,
            return_20d, return_60d, rs_20d_vs_vnindex, rs_60d_vs_vnindex,
            distance_to_52w_high, as_of_bar_date, feature_data_status,
            source_row_count, feature_build_version, feature_generated_at,
            lineage_json, feature_profile, neutral_completeness,
            relative_strength_completeness, required_bar_count,
            observed_bar_count, feature_completeness_rule_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'EXACT_DATE', 120,
                  'fixture-v2', ?, '{"fixture":"production-context"}',
                  'STANDARD_120', 'COMPLETE', 'COMPLETE', 120, 120,
                  'feature-completeness-v1')
        """,
        [
            symbol,
            TARGET_DATE,
            close,
            100.0,
            ma50,
            volume_ma20,
            return20,
            return60,
            rs20,
            rs60,
            -0.002,
            TARGET_DATE,
            GENERATED_AT,
        ],
    )


def _insert_market_universe(
    conn: duckdb.DuckDBPyConnection,
    *,
    count: int,
    positive_count: int,
    above_ma20_count: int,
    above_ma50_count: int,
) -> None:
    for number in range(count):
        _insert_symbol_feature(
            conn,
            f"SYM{number:02d}",
            sector="Market",
            exchange="HOSE" if number % 2 == 0 else "HNX",
            return20=0.02 if number < positive_count else -0.02,
            above_ma20=number < above_ma20_count,
            above_ma50=number < above_ma50_count,
        )


def test_production_market_rejects_five_rows_and_records_policy(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _insert_benchmark(conn, [100.0 + number for number in range(70)])
    _insert_market_universe(
        conn,
        count=5,
        positive_count=5,
        above_ma20_count=5,
        above_ma50_count=5,
    )

    first = build_market_regime(conn, TARGET_DATE, generated_at=GENERATED_AT)
    second = build_market_regime(conn, TARGET_DATE, generated_at=GENERATED_AT)

    expected = GOLDEN["market"]["insufficient_five_rows"]
    assert first == second
    assert first.regime == expected["regime"]
    assert first.quality == expected["quality"]
    assert first.methodology_version == "market-regime-v2"
    assert first.lineage["policy_minimum_eligible_symbols"] == str(
        expected["minimum_eligible_symbols"]
    )
    assert first.breadth_eligible_count == 5
    assert market_issues(first, first, TARGET_DATE, False) == (
        ContextIssue.MARKET_REGIME_INPUT_COVERAGE_INSUFFICIENT,
    )


@pytest.mark.parametrize(
    ("benchmark_closes", "positive", "above20", "above50", "golden_key"),
    [
        ([100.0 + number for number in range(70)], 20, 20, 20, "risk_on"),
        ([170.0 - number for number in range(70)], 4, 4, 4, "risk_off"),
        ([100.0 for _ in range(70)], 10, 10, 10, "mixed"),
    ],
)
def test_production_market_golden_states_are_deterministic(
    conn: duckdb.DuckDBPyConnection,
    benchmark_closes: list[float],
    positive: int,
    above20: int,
    above50: int,
    golden_key: str,
) -> None:
    _insert_benchmark(conn, benchmark_closes)
    _insert_market_universe(
        conn,
        count=20,
        positive_count=positive,
        above_ma20_count=above20,
        above_ma50_count=above50,
    )
    # A non-common security with strong inputs must not change the production universe.
    _insert_symbol_feature(
        conn,
        "ETF01",
        sector="Fund",
        security_type="ETF",
        return20=10.0,
        rs20=10.0,
        volume_ma20=10_000_000.0,
    )

    first = build_market_regime(conn, TARGET_DATE, generated_at=GENERATED_AT)
    second = build_market_regime(conn, TARGET_DATE, generated_at=GENERATED_AT)

    expected = GOLDEN["market"][golden_key]
    assert first == second
    assert first.regime == expected["regime"]
    assert first.quality == expected["quality"]
    assert first.methodology_version == expected["methodology"]
    assert first.breadth_active_count == 20
    assert first.lineage["security_type_excluded_symbols"] == "ETF01"
    assert float(first.lineage["exchange_coverage"]) == pytest.approx(1.0)
    assert float(first.lineage["liquidity_coverage"]) == pytest.approx(1.0)
    assert market_issues(first, first, TARGET_DATE, False) == ()


def test_production_sector_excludes_sparse_and_illiquid_groups(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    for number in range(5):
        _insert_symbol_feature(
            conn,
            f"T{number}",
            sector="Technology",
            volume_ma20=20_000.0 if number < 4 else 500.0,
        )
    for number in range(3):
        _insert_symbol_feature(conn, f"S{number}", sector="Sparse")

    first = build_sector_strength(conn, TARGET_DATE, generated_at=GENERATED_AT)
    second = build_sector_strength(conn, TARGET_DATE, generated_at=GENERATED_AT)

    expected = GOLDEN["sector"]["production"]
    assert first == second
    assert [snapshot.sector for snapshot in first.snapshots] == ["Technology"]
    snapshot = first.snapshots[0]
    assert snapshot.methodology_version == expected["methodology"]
    assert snapshot.member_count == expected["minimum_members"]
    assert snapshot.eligible_count == expected["minimum_eligible"]
    assert float(snapshot.lineage["sector_coverage"]) == pytest.approx(0.8)
    assert float(snapshot.lineage["sector_liquidity_coverage"]) == pytest.approx(0.8)
    assert any("Sparse" in caveat for caveat in first.caveats)
    assert (
        sector_issues(list(first.snapshots), list(first.snapshots), TARGET_DATE, False)
        == ()
    )


def test_production_sector_records_outlier_and_concentration_evidence(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    for number, value, volume in (
        (0, 0.10, 20_000.0),
        (1, 0.11, 20_000.0),
        (2, 0.12, 20_000.0),
        (3, 0.13, 20_000.0),
        (4, 5.00, 2_000_000.0),
    ):
        _insert_symbol_feature(
            conn,
            f"O{number}",
            sector="Outlier",
            return20=value,
            return60=value,
            rs20=value,
            rs60=value / 2,
            volume_ma20=volume,
        )

    result = build_sector_strength(conn, TARGET_DATE, generated_at=GENERATED_AT)
    snapshot = result.snapshots[0]

    expected = GOLDEN["sector"]["outlier_and_concentration"]
    assert (
        int(snapshot.lineage["sector_outlier_adjustment_count"])
        >= expected["minimum_outlier_adjustments"]
    )
    assert float(snapshot.lineage["sector_concentration_ratio"]) > 0.45
    assert expected["concentration_warning"] is True
    assert any("winsorized" in caveat for caveat in snapshot.caveats)
    assert any("concentration" in caveat for caveat in snapshot.caveats)


def test_deep_readiness_rejects_partial_production_sector_metadata(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    for number in range(5):
        _insert_symbol_feature(conn, f"E{number}", sector="Energy")
    for number in range(2):
        _insert_symbol_feature(
            conn,
            f"U{number}",
            sector=None,
            taxonomy=False,
        )

    result = build_sector_strength(conn, TARGET_DATE, generated_at=GENERATED_AT)

    assert result.snapshots
    assert result.quality == "PARTIAL_METADATA"
    assert sector_issues(
        list(result.snapshots), list(result.snapshots), TARGET_DATE, False
    ) == (ContextIssue.SECTOR_METADATA_INSUFFICIENT,)
