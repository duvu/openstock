from __future__ import annotations

from datetime import UTC, date, datetime

import duckdb

from vnalpha.symbol_memory.entity_compaction import EntityMemoryCompactionService
from vnalpha.symbol_memory.models import (
    ClaimOrigin,
    ClaimStatus,
    MemoryClaim,
    MemoryEntity,
    MemoryEntityType,
)
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.retrieval import SymbolMemoryRetrievalService
from vnalpha.warehouse.migrations import run_migrations


def _claim(entity: MemoryEntity, claim_id: str, as_of: date) -> MemoryClaim:
    observed_at = datetime(as_of.year, as_of.month, as_of.day, tzinfo=UTC)
    return MemoryClaim(
        claim_id=claim_id,
        symbol=entity.entity_id
        if entity.entity_type is MemoryEntityType.SYMBOL
        else None,
        claim_type="durable_fact",
        predicate="identity",
        value={"entity_id": entity.entity_id},
        status=ClaimStatus.ACTIVE,
        pinned=False,
        confidence=None,
        observed_at=observed_at,
        as_of_date=as_of,
        valid_from=as_of,
        valid_until=None,
        origin=ClaimOrigin.USER_NOTE,
        source_refs=(),
        correlation_id=f"corr-{claim_id}",
        created_at=observed_at,
        entity_type=entity.entity_type,
        entity_id=entity.entity_id,
    )


def _create_populated_legacy_memory_schema(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    legacy_ddl = (
        "CREATE TABLE memory_event (event_id VARCHAR PRIMARY KEY, symbol VARCHAR "
        "NOT NULL, event_type VARCHAR NOT NULL, evidence_ref VARCHAR, content_hash "
        "VARCHAR NOT NULL, observed_at TIMESTAMPTZ, as_of_date DATE, origin VARCHAR "
        "NOT NULL, correlation_id VARCHAR NOT NULL, created_at TIMESTAMPTZ NOT NULL)",
        "CREATE TABLE memory_claim (claim_id VARCHAR PRIMARY KEY, symbol VARCHAR NOT "
        "NULL, claim_type VARCHAR NOT NULL, predicate VARCHAR NOT NULL, value_json "
        "VARCHAR NOT NULL, status VARCHAR NOT NULL, pinned BOOLEAN NOT NULL, "
        "confidence DOUBLE, observed_at TIMESTAMPTZ, as_of_date DATE, valid_from "
        "DATE, valid_until DATE, origin VARCHAR NOT NULL, source_refs_json VARCHAR "
        "NOT NULL, correlation_id VARCHAR NOT NULL, created_at TIMESTAMPTZ NOT NULL, "
        "supersedes_claim_id VARCHAR, lifecycle_reason VARCHAR, source_published_at DATE)",
        "CREATE TABLE memory_document (symbol VARCHAR PRIMARY KEY, path VARCHAR NOT "
        "NULL, schema_version INTEGER NOT NULL, generation INTEGER NOT NULL, "
        "managed_hash VARCHAR NOT NULL, document_hash VARCHAR NOT NULL, token_estimate "
        "INTEGER NOT NULL, last_compacted_at TIMESTAMPTZ, updated_at TIMESTAMPTZ NOT NULL)",
        "CREATE TABLE memory_compaction_run (compaction_run_id VARCHAR PRIMARY KEY, "
        "symbol VARCHAR NOT NULL, before_generation INTEGER NOT NULL, after_generation "
        "INTEGER NOT NULL, before_hash VARCHAR NOT NULL, after_hash VARCHAR NOT NULL, "
        "retained_claim_count INTEGER NOT NULL, archived_claim_count INTEGER NOT NULL, "
        "conflicted_claim_count INTEGER NOT NULL, before_token_estimate INTEGER NOT "
        "NULL, after_token_estimate INTEGER NOT NULL, source_coverage DOUBLE NOT NULL, "
        "created_at TIMESTAMPTZ NOT NULL, correlation_id VARCHAR NOT NULL)",
    )
    for statement in legacy_ddl:
        conn.execute(statement)
    timestamp = "2026-07-17T08:00:00+07:00"
    conn.execute(
        "INSERT INTO memory_event VALUES "
        "('event-fpt', 'FPT', 'evidence', 'ref-1', 'hash-1', ?, '2026-07-17', "
        "'validated_evidence', 'corr-legacy', ?)",
        [timestamp, timestamp],
    )
    conn.execute(
        "INSERT INTO memory_claim VALUES "
        "('claim-fpt', 'FPT', 'durable_fact', 'identity', '{}', 'active', false, "
        "NULL, ?, '2026-07-17', '2026-07-17', NULL, 'validated_evidence', '[]', "
        "'corr-legacy', ?, NULL, NULL, '2026-07-17')",
        [timestamp, timestamp],
    )
    conn.execute(
        "INSERT INTO memory_document VALUES "
        "('FPT', 'symbols/FPT.md', 1, 3, 'managed', 'document', 42, ?, ?)",
        [timestamp, timestamp],
    )
    conn.execute(
        "INSERT INTO memory_compaction_run VALUES "
        "('compact-fpt', 'FPT', 2, 3, 'before', 'after', 1, 0, 0, 45, 42, "
        "1.0, ?, 'corr-legacy')",
        [timestamp],
    )


def test_legacy_symbol_rows_migrate_to_explicit_entity_identity() -> None:
    conn = duckdb.connect(":memory:")
    _create_populated_legacy_memory_schema(conn)

    run_migrations(conn)
    repository = SymbolMemoryRepository(conn)

    for table in (
        "memory_event",
        "memory_claim",
        "memory_document",
        "memory_compaction_run",
    ):
        assert conn.execute(
            f"SELECT symbol, entity_type, entity_id FROM {table}"
        ).fetchall() == [("FPT", "SYMBOL", "FPT")]
    assert repository.list_claims("fpt")[0].entity == MemoryEntity.symbol("FPT")
    conn.close()


def test_same_text_id_cannot_collide_across_allowlisted_entity_types() -> None:
    conn = duckdb.connect(":memory:")
    run_migrations(conn)
    repository = SymbolMemoryRepository(conn)
    market = MemoryEntity.market("VN")
    sector = MemoryEntity.taxonomy(
        MemoryEntityType.SECTOR,
        code="VN",
        taxonomy_name="ICB",
        taxonomy_version="2024",
    )
    repository.create_claim(_claim(market, "claim-market", date(2026, 7, 17)))
    repository.create_claim(_claim(sector, "claim-sector", date(2026, 7, 17)))

    assert repository.list_entity_claims(market)[0].claim_id == "claim-market"
    assert repository.list_entity_claims(sector)[0].claim_id == "claim-sector"
    assert repository.list_claims("VN") == []
    conn.close()


def test_entity_retrieval_remains_as_of_aware_and_budgeted() -> None:
    conn = duckdb.connect(":memory:")
    run_migrations(conn)
    repository = SymbolMemoryRepository(conn)
    entity = MemoryEntity.asset_class("common_equity")
    repository.create_claim(_claim(entity, "claim-old", date(2026, 7, 16)))
    repository.create_claim(_claim(entity, "claim-future", date(2026, 7, 18)))

    result = SymbolMemoryRetrievalService(repository).retrieve_entity(
        entity,
        as_of_date=date(2026, 7, 17),
        token_budget=1_000,
    )

    assert [claim.claim_id for claim in result.selected_claims] == ["claim-old"]
    assert result.entity == entity
    assert ("claim-future", "future") in result.omitted_claims
    conn.close()


def test_taxonomy_identity_is_versioned_and_bounded() -> None:
    current = MemoryEntity.taxonomy(
        MemoryEntityType.INDUSTRY,
        code="SOFT",
        taxonomy_name="ICB",
        taxonomy_version="2024",
    )
    previous = MemoryEntity.taxonomy(
        MemoryEntityType.INDUSTRY,
        code="SOFT",
        taxonomy_name="ICB",
        taxonomy_version="2019",
    )

    assert current.entity_id == "ICB:2024:SOFT"
    assert current != previous


def test_entity_compaction_uses_collision_safe_paths_and_is_idempotent(
    tmp_path,
) -> None:
    conn = duckdb.connect(":memory:")
    run_migrations(conn)
    repository = SymbolMemoryRepository(conn)
    market = MemoryEntity.market("VN")
    sector = MemoryEntity.taxonomy(
        MemoryEntityType.SECTOR,
        code="VN",
        taxonomy_name="ICB",
        taxonomy_version="2024",
    )
    repository.create_claim(_claim(market, "market-vn", date(2026, 7, 17)))
    repository.create_claim(_claim(sector, "sector-vn", date(2026, 7, 17)))
    compaction = EntityMemoryCompactionService(repository, tmp_path)

    market_first = compaction.compact(market)
    market_second = compaction.compact(market)
    sector_first = compaction.compact(sector)

    assert market_first.changed is True
    assert market_second.changed is False
    assert sector_first.path != market_first.path
    assert repository.get_entity_document(market).generation == 1
    assert repository.get_entity_document(sector).generation == 1
    conn.close()
