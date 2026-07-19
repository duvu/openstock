from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import pytest

from vnalpha.symbol_memory.models import ClaimStatus
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.selective_projection import SelectiveSymbolMemoryProjector
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    connection.execute(
        "INSERT INTO symbol_classification_history ("
        "symbol, effective_from, source_snapshot_id, classification_source, "
        "exchange, security_type, lifecycle_status, sector_code, sector_name, "
        "industry_code, industry_name, taxonomy_name, taxonomy_version) "
        "VALUES ('FPT', '2026-01-01', 'snapshot-240', 'fixture', 'HOSE', "
        "'COMMON_EQUITY', 'ACTIVE', 'TECH', 'Technology', 'SOFT', 'Software', "
        "'ICB', '2024')"
    )
    yield connection
    connection.close()


def _candidate(
    conn: duckdb.DuckDBPyConnection,
    as_of: str,
    *,
    score: float,
    candidate_class: str = "WATCH_CANDIDATE",
    setup_type: str = "ACCUMULATION_BASE",
) -> None:
    conn.execute(
        "INSERT INTO candidate_score ("
        "symbol, date, score, candidate_class, setup_type, risk_flags_json, "
        "scoring_policy_id, scoring_policy_hash, scoring_policy_status) "
        "VALUES ('FPT', ?, ?, ?, ?, '[\"LOW_LIQUIDITY\"]', "
        "'openstock-candidate-score', 'hash-240', 'ACCEPTED')",
        [as_of, score, candidate_class, setup_type],
    )


def test_unchanged_daily_state_creates_no_claim_or_card_generation(
    conn, tmp_path: Path
) -> None:
    _candidate(conn, "2026-07-16", score=0.71)
    _candidate(conn, "2026-07-17", score=0.83)
    projector = SelectiveSymbolMemoryProjector(conn, memory_root=tmp_path)

    first = projector.project(
        ("FPT",), as_of_date=date(2026, 7, 16), correlation_id="corr-240-a"
    )
    document = SymbolMemoryRepository(conn).get_document("FPT")
    assert document is not None

    second = projector.project(
        ("FPT",), as_of_date=date(2026, 7, 17), correlation_id="corr-240-b"
    )
    unchanged = SymbolMemoryRepository(conn).get_document("FPT")

    assert first.counters.claims_created == 2
    assert second.counters.claims_created == 0
    assert second.counters.cards_compacted == 0
    assert unchanged is not None
    assert unchanged.generation == document.generation


def test_changed_setup_supersedes_material_state_without_storing_score(
    conn, tmp_path: Path
) -> None:
    _candidate(conn, "2026-07-16", score=0.71)
    _candidate(
        conn,
        "2026-07-17",
        score=0.99,
        candidate_class="ACTIONABLE_CANDIDATE",
        setup_type="BREAKOUT",
    )
    projector = SelectiveSymbolMemoryProjector(conn, memory_root=tmp_path)
    projector.project(
        ("FPT",), as_of_date=date(2026, 7, 16), correlation_id="corr-240-a"
    )

    changed = projector.project(
        ("FPT",), as_of_date=date(2026, 7, 17), correlation_id="corr-240-b"
    )
    claims = SymbolMemoryRepository(conn).list_claims("FPT")
    candidate_claims = [
        claim for claim in claims if claim.claim_type == "candidate_state"
    ]

    assert changed.counters.claims_created == 1
    assert changed.counters.claims_superseded == 1
    assert {claim.status for claim in candidate_claims} == {
        ClaimStatus.ACTIVE,
        ClaimStatus.SUPERSEDED,
    }
    serialized = json.dumps([dict(claim.value) for claim in candidate_claims])
    assert "0.71" not in serialized
    assert "0.99" not in serialized


def test_deleted_source_rejects_claim_and_expired_state_is_not_current(
    conn, tmp_path: Path
) -> None:
    _candidate(conn, "2026-07-01", score=0.71)
    projector = SelectiveSymbolMemoryProjector(conn, memory_root=tmp_path)
    projector.project(
        ("FPT",), as_of_date=date(2026, 7, 1), correlation_id="corr-240-source"
    )
    conn.execute("DELETE FROM candidate_score WHERE symbol = 'FPT'")

    invalidated = projector.project(
        ("FPT",),
        as_of_date=date(2026, 7, 9),
        correlation_id="corr-240-invalidated",
    )
    candidate_claim = next(
        claim
        for claim in SymbolMemoryRepository(conn).list_claims("FPT")
        if claim.claim_type == "candidate_state"
    )

    assert invalidated.counters.claims_rejected == 1
    assert candidate_claim.status is ClaimStatus.REJECTED


def test_short_lived_state_expires_but_durable_taxonomy_remains_active(
    conn, tmp_path: Path
) -> None:
    _candidate(conn, "2026-07-01", score=0.71)
    projector = SelectiveSymbolMemoryProjector(conn, memory_root=tmp_path)
    projector.project(
        ("FPT",), as_of_date=date(2026, 7, 1), correlation_id="corr-240-expiry-a"
    )

    expired = projector.project(
        ("FPT",), as_of_date=date(2026, 7, 9), correlation_id="corr-240-expiry-b"
    )
    claims = SymbolMemoryRepository(conn).list_claims("FPT")

    assert expired.counters.claims_expired == 1
    assert (
        next(claim for claim in claims if claim.claim_type == "candidate_state").status
        is ClaimStatus.EXPIRED
    )
    assert (
        next(claim for claim in claims if claim.claim_type == "symbol_identity").status
        is ClaimStatus.ACTIVE
    )


def test_unvalidated_score_never_enters_memory(conn, tmp_path: Path) -> None:
    _candidate(conn, "2026-07-17", score=0.71)
    conn.execute(
        "UPDATE candidate_score SET scoring_policy_status = 'REJECTED' "
        "WHERE symbol = 'FPT' AND date = '2026-07-17'"
    )

    result = SelectiveSymbolMemoryProjector(conn, memory_root=tmp_path).project(
        ("FPT",), as_of_date=date(2026, 7, 17), correlation_id="corr-240-rejected"
    )
    claims = SymbolMemoryRepository(conn).list_claims("FPT")

    assert result.failed_symbols == ()
    assert not any(claim.claim_type == "candidate_state" for claim in claims)


def test_invalid_symbol_memory_input_does_not_roll_back_valid_symbol(
    conn, tmp_path: Path
) -> None:
    _candidate(conn, "2026-07-17", score=0.71)

    result = SelectiveSymbolMemoryProjector(conn, memory_root=tmp_path).project(
        ("../invalid", "FPT"),
        as_of_date=date(2026, 7, 17),
        correlation_id="corr-240-isolation",
    )

    assert result.failed_symbols == ("INVALID_SYMBOL",)
    assert result.processed_symbols == ("FPT",)
    assert result.counters.claims_created == 2
