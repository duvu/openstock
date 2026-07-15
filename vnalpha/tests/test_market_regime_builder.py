from __future__ import annotations

import json
from collections.abc import Generator
from datetime import date, datetime, timezone
from math import sqrt
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


def test_build_market_regime_is_constructive_when_uptrend_lacks_risk_on_breadth(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: an upward normal-volatility benchmark with weak MA20 breadth.
    _insert_benchmark(conn, [100.0 + number for number in range(70)])
    _insert_breadth(conn, ma20_count=2, ma50_count=3, positive_count=3)

    # When: the market regime is built.
    snapshot = _build(conn)

    # Then: the uptrend remains constructive rather than risk-on.
    assert snapshot.regime == "CONSTRUCTIVE"
    assert snapshot.quality == "COMPLETE"


def test_build_market_regime_is_risk_off_for_downtrend_with_weak_breadth(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: a downward benchmark and MA20 breadth below forty percent.
    _insert_benchmark(conn, [170.0 - number for number in range(70)])
    _insert_breadth(conn, ma20_count=1, ma50_count=1, positive_count=1)

    # When: the market regime is built.
    snapshot = _build(conn)

    # Then: the state is risk-off.
    assert snapshot.trend == "DOWNTREND"
    assert snapshot.regime == "RISK_OFF"


def test_build_market_regime_marks_missing_benchmark_insufficient(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: exact breadth data but no benchmark bars.
    _insert_breadth(conn)

    # When: the market regime is built.
    snapshot = _build(conn)

    # Then: an insufficient-data snapshot is persisted with a missing-benchmark caveat.
    assert snapshot.regime == "INSUFFICIENT_DATA"
    assert snapshot.quality == "INCOMPLETE"
    assert "Benchmark VNINDEX is unavailable." in snapshot.caveats
    assert get_market_regime_as_of(conn, TARGET_DATE) == snapshot


def test_build_market_regime_marks_short_benchmark_history_insufficient(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: fewer than sixty benchmark bars and otherwise usable breadth.
    _insert_benchmark(conn, [100.0 + number for number in range(59)])
    _insert_breadth(conn)

    # When: the market regime is built.
    snapshot = _build(conn)

    # Then: the history requirement is reflected in quality and caveats.
    assert snapshot.regime == "INSUFFICIENT_DATA"
    assert snapshot.quality == "INCOMPLETE"
    assert "Benchmark history has 59 bars; 60 required." in snapshot.caveats


def test_build_market_regime_classifies_sixty_bars_without_return60(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: sixty benchmark closes that satisfy all required state inputs.
    _insert_benchmark(conn, [100.0 + number for number in range(60)])
    _insert_breadth(conn)

    # When: the market regime is built.
    snapshot = _build(conn)

    # Then: state is classified while the unavailable sixty-session return is explicit.
    assert snapshot.regime == "RISK_ON"
    assert snapshot.return60 is None
    assert snapshot.quality == "INCOMPLETE"
    assert "Benchmark 60-session return is unavailable." in snapshot.caveats


def test_build_market_regime_marks_missing_benchmark_dimension_insufficient(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: sufficient benchmark history whose target close is unavailable.
    _insert_benchmark(conn, [100.0 + number for number in range(70)])
    _insert_breadth(conn)
    conn.execute(
        "UPDATE canonical_ohlcv SET close = NULL WHERE symbol = 'VNINDEX' AND time = ?",
        [TARGET_DATE],
    )

    # When: the market regime is built.
    snapshot = _build(conn)

    # Then: missing trend or volatility inputs produce an insufficient state.
    assert snapshot.regime == "INSUFFICIENT_DATA"
    assert snapshot.trend == "INSUFFICIENT_DATA"
    assert snapshot.volatility == "INSUFFICIENT_DATA"
    assert snapshot.quality == "INCOMPLETE"
    assert "Required benchmark feature values are unavailable." in snapshot.caveats


def test_classify_volatility_marks_annualized_thirty_percent_boundary_high() -> None:
    # Given: rolling volatility exactly at the annualized thirty-percent threshold.
    from vnalpha.research_intelligence.benchmark import classify_volatility

    threshold = 0.30 / sqrt(252)

    # When: the benchmark volatility context is classified.
    volatility = classify_volatility(threshold, required_values_available=True)

    # Then: the inclusive boundary is high volatility.
    assert volatility == "HIGH"


def test_build_market_regime_maps_high_volatility_mixed_trend_to_mixed(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: a high-volatility benchmark without an ordered moving-average trend.
    _insert_benchmark(
        conn, [100.0 if number % 2 == 0 else 104.0 for number in range(70)]
    )
    _insert_breadth(conn)

    # When: the market regime is built.
    snapshot = _build(conn)

    # Then: high volatility is retained while the state remains mixed.
    assert snapshot.volatility == "HIGH"
    assert snapshot.trend == "MIXED"
    assert snapshot.regime == "MIXED"


def test_build_market_regime_excludes_stale_feature_rows_and_marks_breadth_insufficient(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: four exact features, two stale features, and one active symbol without features.
    _insert_benchmark(conn, [100.0 + number for number in range(70)])
    _insert_breadth(conn, count=4, stale_symbols=2)
    upsert_symbol(conn, "MISSING")

    # When: the market regime is built.
    snapshot = _build(conn)

    # Then: only exact usable rows count, and the caveat records the threshold.
    assert snapshot.breadth_active_count == 7
    assert snapshot.breadth_eligible_count == 4
    assert snapshot.breadth_excluded_count == 3
    assert snapshot.breadth_coverage == pytest.approx(4 / 7)
    assert snapshot.pct_above_ma20 is None
    assert snapshot.regime == "INSUFFICIENT_DATA"
    assert "Breadth eligible rows: 4; 5 required." in snapshot.caveats
    assert snapshot.lineage["excluded_symbols"] == "MISSING,STALE00,STALE01"


def test_market_regime_golden_outputs_retain_facts_caveats_and_safe_language(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: representative complete and incomplete breadth contexts and golden claims.
    golden = json.loads(GOLDEN_FIXTURE.read_text())
    _insert_benchmark(conn, [100.0 + number for number in range(70)])
    _insert_breadth(conn)

    # When: the complete market regime context is built.
    healthy = _build(conn)

    # Then: its golden facts and methodology are retained without advisory language.
    expected = golden["healthy_regime"]["expected"]
    assert healthy.regime == expected["market_regime_state"]
    assert healthy.quality == expected["quality_status"]
    assert healthy.breadth_eligible_count == expected["breadth_feature_count"]
    assert healthy.caveats == tuple(expected["caveats"])
    assert healthy.methodology_version == expected["methodology_version"]
    assert healthy.lineage["benchmark_freshness"] == expected["benchmark_freshness"]
    descriptions = " ".join(case["description"] for case in golden.values()).lower()
    assert not any(term in descriptions for term in PROHIBITED_TERMS)


def test_market_regime_golden_incomplete_breadth_retains_caveat(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: exact benchmark history and insufficient eligible breadth.
    golden = json.loads(GOLDEN_FIXTURE.read_text())
    _insert_benchmark(conn, [100.0 + number for number in range(70)])
    _insert_breadth(conn, count=4)

    # When: the regime snapshot is persisted.
    snapshot = _build(conn)

    # Then: the golden incomplete-data evidence remains explicit.
    expected = golden["incomplete_breadth"]["expected"]
    assert snapshot.regime == expected["market_regime_state"]
    assert snapshot.quality == expected["quality_status"]
    assert snapshot.breadth_eligible_count == expected["breadth_feature_count"]
    assert expected["caveat"] in snapshot.caveats
    assert snapshot.methodology_version == expected["methodology_version"]
    assert snapshot.lineage["benchmark_freshness"] == expected["benchmark_freshness"]


def test_build_market_regime_emits_correlated_event_after_persistence(
    conn: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    # Given: a complete context and an existing run correlation.
    from vnalpha.observability.context import (
        init_run_context,
        reset_run_context,
        set_correlation_id,
    )

    reset_run_context()
    run_context = init_run_context("test", actor="test", log_root=tmp_path)
    correlation_id = set_correlation_id()
    _insert_benchmark(conn, [100.0 + number for number in range(70)])
    _insert_breadth(conn)

    try:
        # When: the market regime is successfully persisted.
        snapshot = _build(conn)

        # Then: exactly one build event carries persisted research metadata.
        records = [
            json.loads(line)
            for line in run_context.audit_path.read_text().splitlines()
            if line.strip()
        ]
        events = [
            record
            for record in records
            if record["event_type"] == "MARKET_REGIME_BUILT"
        ]
        assert len(events) == 1
        event = events[0]
        assert event["correlation_id"] == correlation_id
        assert event["metadata"] == {
            "as_of_date": TARGET_DATE.isoformat(),
            "market_regime_state": snapshot.regime,
            "quality_status": snapshot.quality,
            "breadth_feature_count": snapshot.breadth_eligible_count,
            "caveat_count": len(snapshot.caveats),
            "methodology_version": snapshot.methodology_version,
        }
    finally:
        reset_run_context()


def test_build_market_regime_does_not_emit_event_when_persistence_fails(
    conn: duckdb.DuckDBPyConnection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a complete context whose persistence raises an error.
    from vnalpha.observability.context import init_run_context, reset_run_context
    from vnalpha.research_intelligence import regime

    reset_run_context()
    run_context = init_run_context("test", actor="test", log_root=tmp_path)
    _insert_benchmark(conn, [100.0 + number for number in range(70)])
    _insert_breadth(conn)

    def fail_persistence(
        connection: duckdb.DuckDBPyConnection, snapshot: MarketRegimeSnapshot
    ) -> None:
        raise RuntimeError("persistence failed")

    monkeypatch.setattr(regime, "upsert_market_regime_snapshot", fail_persistence)
    try:
        # When: the builder cannot persist the snapshot.
        with pytest.raises(RuntimeError, match="persistence failed"):
            _build(conn)

        # Then: no successful-build event is written.
        assert not run_context.audit_path.exists()
    finally:
        reset_run_context()
