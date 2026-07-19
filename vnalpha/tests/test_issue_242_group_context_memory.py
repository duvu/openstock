from __future__ import annotations

from datetime import UTC, date, datetime

import duckdb
import pytest

from vnalpha.research_intelligence.group_context import (
    GroupContextProjector,
    GroupType,
    build_group_context,
    list_group_context,
)
from vnalpha.research_intelligence.models import MarketRegimeSnapshot
from vnalpha.research_intelligence.sector import build_sector_strength
from vnalpha.symbol_memory.models import MemoryEntity, MemoryEntityType
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.retrieval import SymbolMemoryRetrievalService
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    get_sector_strength_as_of,
    upsert_market_regime_snapshot,
)

AS_OF = date(2026, 7, 17)
GENERATED_AT = datetime(2026, 7, 17, 10, tzinfo=UTC)


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    for index in range(10):
        sector_number = index // 5
        symbol = f"S{index}"
        connection.execute(
            "INSERT INTO symbol_classification_history ("
            "symbol, effective_from, source_snapshot_id, classification_source, "
            "exchange, security_type, lifecycle_status, sector_code, sector_name, "
            "industry_code, industry_name, taxonomy_name, taxonomy_version) "
            "VALUES (?, '2026-01-01', 'snapshot-242', 'fixture', 'HOSE', "
            "'COMMON_EQUITY', 'ACTIVE', ?, ?, ?, ?, 'ICB', '2024')",
            [
                symbol,
                f"SEC{sector_number}",
                f"Sector {sector_number}",
                f"IND{sector_number}",
                f"Industry {sector_number}",
            ],
        )
        connection.execute(
            "INSERT INTO feature_snapshot ("
            "symbol, date, close, ma20, ma50, volume_ma20, return_20d, return_60d, "
            "rs_20d_vs_vnindex, rs_60d_vs_vnindex, as_of_bar_date, "
            "feature_data_status, source_row_count, feature_build_version, "
            "feature_generated_at, lineage_json, feature_profile, "
            "neutral_completeness, relative_strength_completeness, "
            "required_bar_count, observed_bar_count, feature_completeness_rule_version) "
            "VALUES (?, ?, 100, 95, 90, 100000, ?, 0.03, ?, 0.01, ?, "
            "'EXACT_DATE', 120, 'fixture-v1', ?, '{}', 'STANDARD_120', "
            "'COMPLETE', 'COMPLETE', 120, 120, 'feature-completeness-v1')",
            [
                symbol,
                AS_OF,
                0.08 if sector_number == 0 else -0.02,
                0.04 if sector_number == 0 else -0.03,
                AS_OF,
                GENERATED_AT,
            ],
        )
    upsert_market_regime_snapshot(
        connection,
        MarketRegimeSnapshot(
            as_of_date=AS_OF,
            benchmark_symbol="VNINDEX",
            benchmark_bar_date=AS_OF,
            close=1300.0,
            ma20=1280.0,
            ma50=1250.0,
            ma50_slope=1.0,
            return20=0.04,
            return60=0.08,
            volatility20=0.01,
            breadth_active_count=10,
            breadth_eligible_count=10,
            breadth_excluded_count=0,
            breadth_coverage=1.0,
            pct_above_ma20=0.7,
            pct_above_ma50=0.8,
            pct_positive_return20=0.7,
            regime="RISK_ON",
            trend="UP",
            volatility="NORMAL",
            quality="OK",
            caveats=(),
            lineage={"fixture": "242"},
            methodology_version="market-regime-v2",
            generated_at=GENERATED_AT,
        ),
    )
    yield connection
    connection.close()


def test_group_snapshots_are_deterministic_and_sector_policy_compatible(conn) -> None:
    sectors = build_sector_strength(conn, AS_OF, generated_at=GENERATED_AT)

    first = build_group_context(conn, AS_OF, generated_at=GENERATED_AT)
    second = build_group_context(conn, AS_OF, generated_at=GENERATED_AT)

    assert first == second
    persisted_sector = list_group_context(conn, AS_OF, GroupType.SECTOR)
    assert [item.rank for item in persisted_sector] == [
        item.rank for item in get_sector_strength_as_of(conn, AS_OF)
    ]
    assert [item.score for item in persisted_sector] == [
        item.score for item in sectors.snapshots
    ]
    assert {item.group_type for item in first.snapshots} == {
        GroupType.SECTOR,
        GroupType.INDUSTRY,
        GroupType.ASSET_CLASS,
    }


def test_unchanged_group_snapshots_do_not_create_new_entity_memory_generation(
    conn, tmp_path
) -> None:
    build_sector_strength(conn, AS_OF, generated_at=GENERATED_AT)
    build_group_context(conn, AS_OF, generated_at=GENERATED_AT)
    projector = GroupContextProjector(conn, memory_root=tmp_path)

    first = projector.project(AS_OF, correlation_id="corr-242-a")
    second = projector.project(AS_OF, correlation_id="corr-242-b")

    assert first.claims_created > 0
    assert second.claims_created == 0
    assert second.cards_compacted == 0
    entity_types = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT entity_type FROM memory_claim WHERE entity_type != 'SYMBOL'"
        ).fetchall()
    }
    assert entity_types == {
        MemoryEntityType.MARKET.value,
        MemoryEntityType.SECTOR.value,
        MemoryEntityType.INDUSTRY.value,
        MemoryEntityType.ASSET_CLASS.value,
    }

    sector = list_group_context(conn, AS_OF, GroupType.SECTOR)[0]
    context = SymbolMemoryRetrievalService(
        SymbolMemoryRepository(conn)
    ).retrieve_with_context(
        "S0",
        (
            MemoryEntity.market(),
            MemoryEntity(MemoryEntityType.SECTOR, sector.entity_id),
            MemoryEntity.asset_class("COMMON_EQUITY"),
        ),
        as_of_date=AS_OF,
        token_budget=4_000,
    )
    assert {result.entity.entity_type for result in context.results} == {
        MemoryEntityType.SYMBOL,
        MemoryEntityType.MARKET,
        MemoryEntityType.SECTOR,
        MemoryEntityType.ASSET_CLASS,
    }
    assert context.token_estimate <= 4_000


def test_changed_rotation_supersedes_group_memory(conn, tmp_path) -> None:
    build_sector_strength(conn, AS_OF, generated_at=GENERATED_AT)
    build_group_context(conn, AS_OF, generated_at=GENERATED_AT)
    projector = GroupContextProjector(conn, memory_root=tmp_path)
    projector.project(AS_OF, correlation_id="corr-242-first")
    conn.execute(
        "UPDATE feature_snapshot SET rs_20d_vs_vnindex = -0.04, "
        "rs_60d_vs_vnindex = -0.01 WHERE symbol IN "
        "('S0', 'S1', 'S2', 'S3', 'S4') AND date = ?",
        [AS_OF],
    )
    build_sector_strength(conn, AS_OF, generated_at=GENERATED_AT)
    changed = build_group_context(conn, AS_OF, generated_at=GENERATED_AT)

    result = projector.project(AS_OF, correlation_id="corr-242-changed")

    assert any(
        item.rotation == "WEAKENING"
        for item in changed.snapshots
        if item.group_type is GroupType.SECTOR
    )
    assert result.claims_created > 0
    assert result.claims_superseded > 0


def test_future_taxonomy_change_does_not_rewrite_historical_group_snapshot(
    conn,
) -> None:
    build_sector_strength(conn, AS_OF, generated_at=GENERATED_AT)
    before = build_group_context(conn, AS_OF, generated_at=GENERATED_AT)
    conn.execute(
        "UPDATE symbol_classification_history SET effective_to = '2026-07-18' "
        "WHERE symbol = 'S0' AND effective_from = '2026-01-01'"
    )
    conn.execute(
        "INSERT INTO symbol_classification_history ("
        "symbol, effective_from, source_snapshot_id, classification_source, "
        "exchange, security_type, lifecycle_status, sector_code, sector_name, "
        "industry_code, industry_name, taxonomy_name, taxonomy_version) "
        "VALUES ('S0', '2026-07-18', 'snapshot-242-future', 'fixture', 'HOSE', "
        "'COMMON_EQUITY', 'ACTIVE', 'SEC9', 'Future Sector', 'IND9', "
        "'Future Industry', 'ICB', '2025')"
    )
    build_sector_strength(conn, AS_OF, generated_at=GENERATED_AT)

    after = build_group_context(conn, AS_OF, generated_at=GENERATED_AT)

    assert after == before


def test_low_coverage_groups_are_excluded_with_caveats(conn) -> None:
    conn.execute(
        "DELETE FROM feature_snapshot WHERE symbol IN ('S5', 'S6') AND date = ?",
        [AS_OF],
    )
    build_sector_strength(conn, AS_OF, generated_at=GENERATED_AT)

    result = build_group_context(conn, AS_OF, generated_at=GENERATED_AT)

    industries = {
        item.group_code
        for item in result.snapshots
        if item.group_type is GroupType.INDUSTRY
    }
    assert "IND1" not in industries
    assert any("eligible members" in caveat for caveat in result.caveats)
