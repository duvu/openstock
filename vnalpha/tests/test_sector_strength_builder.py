from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pytest

from vnalpha.research_intelligence.models import SectorStrengthSnapshot
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    get_sector_strength_as_of,
    get_symbol_sector_alignment,
    upsert_symbol,
)

TARGET_DATE = date(2024, 6, 28)
GENERATED_AT = datetime(2024, 6, 29, tzinfo=timezone.utc)
GOLDEN_FIXTURE = Path(__file__).parent / "fixtures" / "sector_context_golden.json"
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


@dataclass(frozen=True, slots=True)
class FeatureFixture:
    symbol: str
    sector: str | None
    return20: float = 0.10
    return60: float = 0.05
    rs20: float = 0.02
    rs60: float = 0.01
    above_ma20: bool = True
    above_ma50: bool = True
    exact: bool = True


@pytest.fixture
def conn() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _insert_feature(conn: duckdb.DuckDBPyConnection, fixture: FeatureFixture) -> None:
    upsert_symbol(conn, fixture.symbol, sector=fixture.sector)
    close = 101.0 if fixture.above_ma20 else 99.0
    ma50 = 100.0 if fixture.above_ma50 else 102.0
    as_of_bar_date = TARGET_DATE if fixture.exact else date(2024, 6, 27)
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, close, ma20, ma50, return_20d, return_60d,
            rs_20d_vs_vnindex, rs_60d_vs_vnindex, as_of_bar_date,
            feature_data_status, source_row_count, feature_build_version,
            feature_generated_at, lineage_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            fixture.symbol,
            TARGET_DATE,
            close,
            100.0,
            ma50,
            fixture.return20,
            fixture.return60,
            fixture.rs20,
            fixture.rs60,
            as_of_bar_date,
            "EXACT_DATE" if fixture.exact else "STALE_DATE",
            70,
            "fixture-v1",
            GENERATED_AT,
            '{"fixture":"sector"}',
        ],
    )


def _build(conn: duckdb.DuckDBPyConnection):
    from vnalpha.research_intelligence.sector import build_sector_strength

    return build_sector_strength(conn, TARGET_DATE, generated_at=GENERATED_AT)


def test_build_sector_strength_ranks_tied_scores_alphabetically_and_persists(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: two eligible sectors with identical aggregate measurements.
    for sector in ("Beta", "Alpha"):
        for number in range(3):
            _insert_feature(conn, FeatureFixture(f"{sector[:1]}{number}", sector))

    # When: the same dated context is built twice with a fixed timestamp.
    first = _build(conn)
    second = _build(conn)

    # Then: alphabetic ordering breaks the score and RS tie deterministically.
    assert first == second
    assert [snapshot.sector for snapshot in first.snapshots] == ["Alpha", "Beta"]
    assert [snapshot.rank for snapshot in first.snapshots] == [1, 2]
    assert get_sector_strength_as_of(conn, TARGET_DATE) == list(first.snapshots)


def test_build_sector_strength_uses_three_member_boundary_and_omits_undersized_sector(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: one sector at the rankable boundary and one below it.
    for number in range(3):
        _insert_feature(conn, FeatureFixture(f"T{number}", "Technology"))
    for number in range(2):
        _insert_feature(conn, FeatureFixture(f"S{number}", "Small"))

    # When: sector strength is built.
    result = _build(conn)

    # Then: only the three-member sector is ranked, with an explicit caveat.
    assert [snapshot.sector for snapshot in result.snapshots] == ["Technology"]
    assert result.snapshots[0].member_count == 3
    assert result.snapshots[0].eligible_count == 3
    assert "Small has 2 eligible members; 3 required." in result.caveats


def test_build_sector_strength_computes_medians_score_and_metadata_coverage(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: classified, unclassified, and stale active feature contexts.
    for number, return20, rs20 in ((0, 0.00, -0.01), (1, 0.10, 0.02), (2, 0.30, 0.04)):
        _insert_feature(
            conn,
            FeatureFixture(
                f"E{number}",
                "Energy",
                return20=return20,
                return60=0.20,
                rs20=rs20,
                rs60=0.01,
                above_ma20=number != 0,
                above_ma50=number == 2,
            ),
        )
    _insert_feature(conn, FeatureFixture("BLANK", ""))
    _insert_feature(conn, FeatureFixture("STALE", "Energy", exact=False))

    # When: sector strength is built from exact usable rows.
    result = _build(conn)
    snapshot = result.snapshots[0]

    # Then: medians, breadth proxies, score, and partial metadata are truthful.
    assert snapshot.median_return20 == pytest.approx(0.10)
    assert snapshot.median_return60 == pytest.approx(0.20)
    assert snapshot.median_rs20_vs_vnindex == pytest.approx(0.02)
    assert snapshot.median_rs60_vs_vnindex == pytest.approx(0.01)
    assert snapshot.pct_above_ma20 == pytest.approx(2 / 3)
    assert snapshot.pct_above_ma50 == pytest.approx(1 / 3)
    assert snapshot.leadership_count == 2
    assert snapshot.score == pytest.approx(0.138)
    assert snapshot.metadata_coverage == pytest.approx(3 / 4)
    assert snapshot.unclassified_count == 1
    assert snapshot.quality == "PARTIAL_METADATA"
    assert result.lineage["excluded_symbols"] == "STALE"


@pytest.mark.parametrize(
    ("sector", "rs20", "rs60", "expected_rotation"),
    [
        ("Improving", 0.02, 0.01, "IMPROVING"),
        ("Weakening", -0.02, -0.01, "WEAKENING"),
        ("Stable", 0.02, 0.02, "STABLE"),
    ],
)
def test_build_sector_strength_assigns_rotation_from_median_relative_strength(
    conn: duckdb.DuckDBPyConnection,
    sector: str,
    rs20: float,
    rs60: float,
    expected_rotation: str,
) -> None:
    # Given: three exact members with one relative-strength relationship.
    for number in range(3):
        _insert_feature(
            conn,
            FeatureFixture(f"{sector[:1]}{number}", sector, rs20=rs20, rs60=rs60),
        )

    # When: the snapshot is built.
    snapshot = _build(conn).snapshots[0]

    # Then: rotation follows the methodology's strict comparisons.
    assert snapshot.rotation == expected_rotation


def test_build_sector_strength_returns_insufficient_quality_when_no_sector_is_rankable(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: eligible symbols distributed across sectors below the threshold.
    for number in range(2):
        _insert_feature(conn, FeatureFixture(f"F{number}", "Financials"))
    _insert_feature(conn, FeatureFixture("MISSING", None))

    # When: sector strength is built.
    result = _build(conn)

    # Then: no synthetic snapshot is persisted and the limitation is explicit.
    assert result.snapshots == ()
    assert result.quality == "INSUFFICIENT_DATA"
    assert "No sector has 3 classified eligible members." in result.caveats
    assert get_sector_strength_as_of(conn, TARGET_DATE) == []


def test_sector_alignment_does_not_fabricate_snapshots_for_blank_or_missing_symbols(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: a blank-sector eligible symbol and a missing symbol identifier.
    _insert_feature(conn, FeatureFixture("BLANK", ""))

    # When: alignment is requested after a build with no rankable sector.
    _build(conn)
    blank_alignment = get_symbol_sector_alignment(conn, "BLANK", TARGET_DATE)

    # Then: neither case is mapped to an invented sector snapshot.
    assert blank_alignment is not None
    assert blank_alignment.snapshot is None
    assert get_symbol_sector_alignment(conn, "NOT_LISTED", TARGET_DATE) is None


def test_sector_context_golden_ranking_retains_facts_and_safe_language(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: tied complete sector inputs and a golden research-output contract.
    golden = json.loads(GOLDEN_FIXTURE.read_text())
    for sector in ("Beta", "Alpha"):
        for number in range(3):
            _insert_feature(conn, FeatureFixture(f"{sector[:1]}{number}", sector))

    # When: the sector contexts are persisted.
    result = _build(conn)

    # Then: rank, metadata, quality, and methodology agree with golden facts.
    expected = golden["classified_sector_ranking"]["expected"]
    assert len(result.snapshots) == expected["ranked_sector_count"]
    assert [snapshot.sector for snapshot in result.snapshots] == expected["sectors"]
    assert result.snapshots[0].metadata_coverage == pytest.approx(
        expected["metadata_coverage_pct"]
    )
    assert result.snapshots[0].unclassified_count == expected["unclassified_count"]
    assert result.quality == expected["quality_status"]
    assert (
        result.snapshots[0].lineage["feature_data_freshness"]
        == expected["feature_data_freshness"]
    )
    assert (
        result.snapshots[0].lineage["feature_bar_date_basis"]
        == expected["feature_bar_date_basis"]
    )
    assert result.snapshots[0].methodology_version == expected["methodology_version"]
    descriptions = " ".join(case["description"] for case in golden.values()).lower()
    assert not any(term in descriptions for term in PROHIBITED_TERMS)


def test_sector_context_golden_incomplete_metadata_retains_caveat(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # Given: one rankable classified sector and one blank sector metadata value.
    golden = json.loads(GOLDEN_FIXTURE.read_text())
    for number in range(3):
        _insert_feature(conn, FeatureFixture(f"E{number}", "Energy"))
    _insert_feature(conn, FeatureFixture("BLANK", ""))

    # When: sector strength is persisted.
    result = _build(conn)

    # Then: partial metadata evidence is retained in the result and snapshot.
    expected = golden["incomplete_sector_metadata"]["expected"]
    snapshot = result.snapshots[0]
    assert len(result.snapshots) == expected["ranked_sector_count"]
    assert snapshot.metadata_coverage == pytest.approx(
        expected["metadata_coverage_pct"]
    )
    assert snapshot.unclassified_count == expected["unclassified_count"]
    assert result.quality == expected["quality_status"]
    assert expected["caveat"] in result.caveats
    assert (
        snapshot.lineage["feature_data_freshness"] == expected["feature_data_freshness"]
    )
    assert (
        snapshot.lineage["feature_bar_date_basis"] == expected["feature_bar_date_basis"]
    )
    assert snapshot.methodology_version == expected["methodology_version"]


def test_build_sector_strength_emits_correlated_event_for_no_rankable_persistence(
    conn: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    # Given: no rankable sector and an existing run correlation.
    from vnalpha.observability.context import (
        init_run_context,
        reset_run_context,
        set_correlation_id,
    )

    reset_run_context()
    run_context = init_run_context("test", actor="test", log_root=tmp_path)
    correlation_id = set_correlation_id()
    for number in range(2):
        _insert_feature(conn, FeatureFixture(f"F{number}", "Financials"))

    try:
        # When: the empty sector result is authoritatively persisted.
        result = _build(conn)

        # Then: one event records the persisted insufficient-data result.
        records = [
            json.loads(line)
            for line in run_context.audit_path.read_text().splitlines()
            if line.strip()
        ]
        events = [
            record
            for record in records
            if record["event_type"] == "SECTOR_STRENGTH_BUILT"
        ]
        assert len(events) == 1
        event = events[0]
        assert event["correlation_id"] == correlation_id
        assert event["metadata"] == {
            "as_of_date": TARGET_DATE.isoformat(),
            "ranked_sector_count": len(result.snapshots),
            "metadata_coverage_pct": 1.0,
            "unclassified_count": 0,
            "quality_status": result.quality,
            "methodology_version": "sector-strength-v1",
        }
    finally:
        reset_run_context()


def test_build_sector_strength_does_not_emit_event_when_persistence_fails(
    conn: duckdb.DuckDBPyConnection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a no-rankable context whose authoritative replacement raises an error.
    from vnalpha.observability.context import init_run_context, reset_run_context
    from vnalpha.research_intelligence import sector

    reset_run_context()
    run_context = init_run_context("test", actor="test", log_root=tmp_path)
    for number in range(2):
        _insert_feature(conn, FeatureFixture(f"F{number}", "Financials"))

    def fail_persistence(
        connection: duckdb.DuckDBPyConnection,
        as_of_date: date,
        snapshots: tuple[SectorStrengthSnapshot, ...],
    ) -> None:
        raise RuntimeError("persistence failed")

    monkeypatch.setattr(sector, "replace_sector_strength_snapshots", fail_persistence)
    try:
        # When: the empty build result cannot be persisted.
        with pytest.raises(RuntimeError, match="persistence failed"):
            _build(conn)

        # Then: no successful-build event is written.
        assert not run_context.audit_path.exists()
    finally:
        reset_run_context()


def test_build_sector_strength_persists_empty_universe_and_emits_event(
    conn: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    # Given: a migrated warehouse with no active symbols and an existing correlation.
    from vnalpha.observability.context import (
        init_run_context,
        reset_run_context,
        set_correlation_id,
    )

    reset_run_context()
    run_context = init_run_context("test", actor="test", log_root=tmp_path)
    correlation_id = set_correlation_id()

    try:
        # When: sector strength is built for the empty universe.
        result = _build(conn)

        # Then: the persisted insufficient-data result emits one explicit event.
        assert result.snapshots == ()
        assert result.quality == "INSUFFICIENT_DATA"
        assert get_sector_strength_as_of(conn, TARGET_DATE) == []
        records = [
            json.loads(line)
            for line in run_context.audit_path.read_text().splitlines()
            if line.strip()
        ]
        events = [
            record
            for record in records
            if record["event_type"] == "SECTOR_STRENGTH_BUILT"
        ]
        assert len(events) == 1
        assert events[0]["correlation_id"] == correlation_id
        assert events[0]["metadata"] == {
            "as_of_date": TARGET_DATE.isoformat(),
            "ranked_sector_count": 0,
            "metadata_coverage_pct": 0.0,
            "unclassified_count": 0,
            "quality_status": "INSUFFICIENT_DATA",
            "methodology_version": "sector-strength-v1",
        }
    finally:
        reset_run_context()
