from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone

import duckdb
import pytest

from vnalpha.symbol_memory.ingestion import (
    MemoryEvidence,
    MemoryIngestionError,
    SymbolMemoryIngestionService,
)
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.warehouse.migrations import run_migrations


def _service() -> SymbolMemoryIngestionService:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    connection.execute(
        "INSERT INTO candidate_score (symbol, date, score, candidate_class) "
        "VALUES ('FPT', '2026-07-13', 0.82, 'WATCH_CANDIDATE')"
    )
    return SymbolMemoryIngestionService(SymbolMemoryRepository(connection))


def _evidence() -> MemoryEvidence:
    return MemoryEvidence(
        symbol="FPT",
        claim_type="durable_fact",
        predicate="research_state",
        value={"state": "watch"},
        source_ref="candidate_score:FPT:2026-07-13",
        observed_at=datetime(2026, 7, 13, 11, 0, tzinfo=timezone.utc),
        as_of_date=date(2026, 7, 13),
        confidence=None,
        correlation_id="memory-boundary-001",
    )


def test_unknown_source_kind_is_rejected_before_memory_persistence() -> None:
    service = _service()

    with pytest.raises(MemoryIngestionError, match="persisted source kind"):
        service.ingest_evidence(
            replace(_evidence(), source_ref="persisted_artifact:forged")
        )

    assert service.repository.list_events("FPT") == []
    assert service.repository.list_claims("FPT") == []
