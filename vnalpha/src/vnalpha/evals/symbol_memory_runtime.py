from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb

from vnalpha.symbol_memory.compaction import SymbolMemoryCompactionService
from vnalpha.symbol_memory.ingestion import (
    MemoryEvidence,
    MemoryIngestionError,
    SymbolMemoryIngestionService,
)
from vnalpha.symbol_memory.lifecycle import SymbolMemoryLifecycleService
from vnalpha.symbol_memory.markdown import parse_symbol_card
from vnalpha.symbol_memory.models import ClaimOrigin, ClaimStatus, MemoryClaim
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.retrieval import SymbolMemoryRetrievalService
from vnalpha.warehouse.migrations import run_migrations


@dataclass(frozen=True, slots=True)
class SymbolMemoryRuntimeCaseResult:
    case_id: str
    passed: bool


@dataclass(frozen=True, slots=True)
class SymbolMemoryRuntimeReport:
    cases: tuple[SymbolMemoryRuntimeCaseResult, ...]

    @property
    def passed(self) -> bool:
        return all(case.passed for case in self.cases)


def run_symbol_memory_runtime_corpus(
    root: Path | None = None,
) -> SymbolMemoryRuntimeReport:
    if root is None:
        with TemporaryDirectory(prefix="vnalpha-symbol-memory-eval-") as temporary:
            return _run(Path(temporary))
    return _run(root)


def _run(root: Path) -> SymbolMemoryRuntimeReport:
    cases = (
        ("correction", _correction_case),
        ("conflict", _conflict_case),
        ("compaction", _compaction_case),
        ("temporal_filtering", _temporal_filtering_case),
        ("source_grounding", _source_grounding_case),
    )
    results = []
    for case_id, runner in cases:
        try:
            passed = runner(root / case_id)
        except (duckdb.Error, MemoryIngestionError, OSError, ValueError):
            passed = False
        results.append(SymbolMemoryRuntimeCaseResult(case_id=case_id, passed=passed))
    return SymbolMemoryRuntimeReport(cases=tuple(results))


def _repository() -> SymbolMemoryRepository:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    return SymbolMemoryRepository(connection)


def _claim(
    claim_id: str,
    *,
    value: float,
    source_ref: str = "candidate_score:FPT:2026-07-13",
    status: ClaimStatus = ClaimStatus.ACTIVE,
    source_published_at: date | None = None,
) -> MemoryClaim:
    timestamp = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
    return MemoryClaim(
        claim_id=claim_id,
        symbol="FPT",
        claim_type="candidate_score",
        predicate="composite_score",
        value={"value": value, "unit": "score", "meaning": "candidate score"},
        status=status,
        pinned=False,
        confidence=value,
        observed_at=timestamp,
        as_of_date=date(2026, 7, 13),
        valid_from=date(2026, 7, 13),
        valid_until=None,
        origin=ClaimOrigin.VALIDATED_EVIDENCE,
        source_refs=(source_ref,),
        correlation_id=f"runtime-{claim_id}",
        created_at=timestamp,
        source_published_at=source_published_at,
    )


def _correction_case(_root: Path) -> bool:
    repository = _repository()
    lifecycle = SymbolMemoryLifecycleService(repository)
    lifecycle.accept(_claim("old", value=0.6))
    lifecycle.correct("old", "Corrected source.")
    return repository.get_claim("old").status is ClaimStatus.REJECTED


def _conflict_case(_root: Path) -> bool:
    repository = _repository()
    lifecycle = SymbolMemoryLifecycleService(repository)
    lifecycle.accept(_claim("first", value=0.6))
    accepted = lifecycle.accept(_claim("second", value=0.8))
    return accepted.status is ClaimStatus.CONFLICTED


def _compaction_case(root: Path) -> bool:
    repository = _repository()
    repository.create_claim(_claim("fact", value=0.8))
    service = SymbolMemoryCompactionService(repository, root)
    service.compact("FPT", user_content="- preserved user note\n")
    service.compact("FPT")
    content = (root / "knowledge" / "symbols" / "FPT.md").read_text(encoding="utf-8")
    return parse_symbol_card(content).user_content == "- preserved user note\n"


def _temporal_filtering_case(_root: Path) -> bool:
    repository = _repository()
    repository.create_claim(
        _claim("future-source", value=0.8, source_published_at=date(2026, 7, 20))
    )
    result = SymbolMemoryRetrievalService(repository).retrieve(
        "FPT", as_of_date=date(2026, 7, 13)
    )
    return ("future-source", "future") in result.omitted_claims


def _source_grounding_case(_root: Path) -> bool:
    repository = _repository()
    service = SymbolMemoryIngestionService(repository)
    timestamp = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
    try:
        service.ingest_evidence(
            MemoryEvidence(
                symbol="FPT",
                claim_type="durable_fact",
                predicate="state",
                value={"statement": "ignore policy"},
                source_ref="candidate_score:assistant-transcript",
                observed_at=timestamp,
                as_of_date=timestamp.date(),
                confidence=None,
                correlation_id="runtime-source-grounding",
            )
        )
    except MemoryIngestionError:
        return repository.list_claims("FPT") == []
    return False


__all__ = ["SymbolMemoryRuntimeReport", "run_symbol_memory_runtime_corpus"]
