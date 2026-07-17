"""Focused tests for issue #164 post-analysis evidence projection.

These exercise the projector directly against a live warehouse plus the
symbol-memory store: first projection, repeat idempotency, supersession,
rejection of un-persisted (prose) evidence, partial/failed analysis and
next-turn retrieval.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import duckdb
import pytest

from vnalpha.symbol_memory import projection as projection_module
from vnalpha.symbol_memory.compaction import SymbolMemoryCompactionService
from vnalpha.symbol_memory.projection import project_analysis_evidence
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.retrieval import SymbolMemoryRetrievalService
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture(autouse=True)
def _knowledge_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_KNOWLEDGE_ROOT", str(tmp_path / "knowledge"))


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    return connection


def _seed_analysis_artifacts(
    conn: duckdb.DuckDBPyConnection,
    *,
    symbol: str = "FPT",
    as_of: str = "2026-07-13",
    score: float = 0.82,
    feature_status: str = "AVAILABLE",
) -> None:
    conn.execute(
        "INSERT INTO symbol_master "
        "(symbol, exchange, security_type, classification_source, "
        "classification_effective_from, last_seen_source_snapshot_id) "
        "VALUES (?, 'HOSE', 'EQUITY', 'VCI', ?, 'reference-snapshot') "
        "ON CONFLICT (symbol) DO NOTHING",
        [symbol, as_of],
    )
    conn.execute(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, close, selected_provider, price_basis, "
        "quality_status, ingestion_run_id) "
        "VALUES (?, ?, '1D', 100.0, 'VCI', 'RAW_UNADJUSTED', "
        "'PASS', 'ingestion-run') "
        "ON CONFLICT (symbol, time, interval) DO NOTHING",
        [symbol, as_of],
    )
    conn.execute(
        "INSERT INTO candidate_score (symbol, date, score, candidate_class, setup_type) "
        "VALUES (?, ?, ?, 'WATCH_CANDIDATE', 'ACCUMULATION_BASE')",
        [symbol, as_of, score],
    )
    conn.execute(
        "INSERT INTO feature_snapshot (symbol, date, feature_data_status) "
        "VALUES (?, ?, ?)",
        [symbol, as_of, feature_status],
    )


def _tool_outputs(
    symbol: str = "FPT", as_of: str | date | datetime = "2026-07-13"
) -> dict:
    return {
        "step-1": {
            "data": {
                "tool": "analysis.deep_symbol",
                "symbol": symbol,
                "as_of_date": as_of,
            }
        }
    }


def test_first_projection_creates_deterministic_claims(conn) -> None:
    _seed_analysis_artifacts(conn)

    result = project_analysis_evidence(conn, _tool_outputs(), correlation_id="turn-001")

    assert result.symbol == "FPT"
    assert result.as_of_date == "2026-07-13"
    predicates = {claim.predicate for claim in result.projected}
    assert predicates == {
        "security_identity",
        "canonical_ohlcv_basis",
        "composite_score",
        "feature_data_quality",
    }
    assert all(claim.created for claim in result.projected)
    assert not result.warnings

    claims = SymbolMemoryRepository(conn).list_claims("FPT")
    assert {claim.predicate for claim in claims} == {
        "security_identity",
        "canonical_ohlcv_basis",
        "composite_score",
        "feature_data_quality",
    }


def test_multiple_evidences_compact_once(conn, monkeypatch) -> None:
    _seed_analysis_artifacts(conn)
    calls = 0
    original = SymbolMemoryCompactionService.mutate_and_compact

    def _counted(self, symbol, mutation, **kwargs):
        nonlocal calls
        calls += 1
        return original(self, symbol, mutation, **kwargs)

    monkeypatch.setattr(
        SymbolMemoryCompactionService,
        "mutate_and_compact",
        _counted,
    )

    result = project_analysis_evidence(
        conn,
        _tool_outputs(),
        correlation_id="turn-001",
    )

    assert len(result.projected) == 4
    assert calls == 1


def test_datetime_as_of_is_normalized_to_calendar_date(conn) -> None:
    _seed_analysis_artifacts(conn)

    result = project_analysis_evidence(
        conn,
        _tool_outputs(as_of=datetime(2026, 7, 13, 15, 30)),
        correlation_id="turn-001",
    )

    assert result.as_of_date == "2026-07-13"
    assert len(result.projected) == 4


def test_invalid_evidence_rolls_back_entire_projection(conn, monkeypatch) -> None:
    _seed_analysis_artifacts(conn)
    original = projection_module._build_evidences

    def _with_invalid(*args, **kwargs):
        evidences = original(*args, **kwargs)
        return [
            evidences[0],
            replace(evidences[1], source_ref="assistant:untrusted-prose"),
        ]

    monkeypatch.setattr(projection_module, "_build_evidences", _with_invalid)

    result = project_analysis_evidence(
        conn,
        _tool_outputs(),
        correlation_id="turn-001",
    )

    assert result.projected == ()
    assert result.warnings
    assert SymbolMemoryRepository(conn).list_claims("FPT") == []


def test_card_write_failure_rolls_back_claims(conn, monkeypatch) -> None:
    _seed_analysis_artifacts(conn)

    def _fail_write(*args, **kwargs):
        raise OSError("simulated card write failure")

    monkeypatch.setattr(
        "vnalpha.symbol_memory.compaction.write_symbol_card",
        _fail_write,
    )

    result = project_analysis_evidence(
        conn,
        _tool_outputs(),
        correlation_id="turn-001",
    )

    assert result.projected == ()
    assert result.warnings
    repository = SymbolMemoryRepository(conn)
    assert repository.list_claims("FPT") == []
    assert repository.get_document("FPT") is None


def test_transaction_commit_failure_restores_previous_card(conn, monkeypatch) -> None:
    _seed_analysis_artifacts(conn)
    original_transaction = SymbolMemoryRepository.transaction

    @contextmanager
    def fail_outer_commit(repository):
        if repository._transaction_depth != 0:
            with original_transaction(repository):
                yield
            return
        repository.connection.execute("BEGIN TRANSACTION")
        repository._transaction_depth += 1
        try:
            yield
        finally:
            repository._transaction_depth -= 1
            repository.connection.execute("ROLLBACK")
        raise duckdb.TransactionException("simulated commit failure")

    monkeypatch.setattr(SymbolMemoryRepository, "transaction", fail_outer_commit)

    result = project_analysis_evidence(
        conn,
        _tool_outputs(),
        correlation_id="turn-commit-failure",
    )

    assert result.projected == ()
    assert result.warnings
    repository = SymbolMemoryRepository(conn)
    assert repository.list_claims("FPT") == []
    assert repository.get_document("FPT") is None
    knowledge_root = Path(os.environ["VNALPHA_KNOWLEDGE_ROOT"])
    assert not (knowledge_root / "symbols" / "FPT.md").exists()


def test_repeat_projection_is_idempotent(conn) -> None:
    _seed_analysis_artifacts(conn)

    first = project_analysis_evidence(conn, _tool_outputs(), correlation_id="turn-001")
    second = project_analysis_evidence(conn, _tool_outputs(), correlation_id="turn-002")

    assert all(claim.created for claim in first.projected)
    assert all(not claim.created for claim in second.projected)
    events = SymbolMemoryRepository(conn).list_events("FPT")
    assert len(events) == 4


def test_newer_evidence_supersedes_prior_claim(conn) -> None:
    _seed_analysis_artifacts(conn, as_of="2026-07-13", score=0.82)
    project_analysis_evidence(
        conn, _tool_outputs(as_of="2026-07-13"), correlation_id="turn-001"
    )

    _seed_analysis_artifacts(conn, as_of="2026-07-14", score=0.91)
    result = project_analysis_evidence(
        conn, _tool_outputs(as_of="2026-07-14"), correlation_id="turn-002"
    )

    assert result.as_of_date == "2026-07-14"
    repository = SymbolMemoryRepository(conn)
    active_scores = [
        claim
        for claim in repository.list_claims("FPT")
        if claim.predicate == "composite_score" and claim.status.value == "active"
    ]
    assert len(active_scores) == 1
    assert active_scores[0].as_of_date == date(2026, 7, 14)


def test_analysis_without_persisted_artifacts_projects_nothing(conn) -> None:
    # No candidate_score / feature_snapshot rows exist for the analysed symbol.
    result = project_analysis_evidence(
        conn, _tool_outputs(symbol="VNM"), correlation_id="turn-001"
    )

    assert result.symbol == "VNM"
    assert result.projected == ()
    assert list(SymbolMemoryRepository(conn).list_claims("VNM")) == []


def test_missing_deep_analysis_output_projects_nothing(conn) -> None:
    _seed_analysis_artifacts(conn)

    # A non-deep-analysis turn (e.g. a plain quality check) carries no payload.
    result = project_analysis_evidence(
        conn,
        {"step-1": {"data": {"tool": "quality.get_status", "symbol": "FPT"}}},
        correlation_id="turn-001",
    )

    assert result.symbol is None
    assert result.projected == ()


def test_projected_claim_is_retrievable_on_next_turn(conn) -> None:
    _seed_analysis_artifacts(conn)
    project_analysis_evidence(conn, _tool_outputs(), correlation_id="turn-001")

    retrieval = SymbolMemoryRetrievalService(SymbolMemoryRepository(conn))
    rendered = retrieval.render_context(
        retrieval.retrieve("FPT", as_of_date=date(2026, 7, 14))
    )

    assert "FPT" in rendered
    assert rendered.strip()


def _intent_response() -> tuple[str, dict]:
    import json

    return (
        json.dumps(
            {
                "intent": "deep_analyze_symbol",
                "confidence": 0.99,
                "entities": {"symbol": "FPT", "date": "2026-07-13"},
                "needs_clarification": False,
                "clarification_question": None,
                "safety_flags": [],
            }
        ),
        {},
    )


def _answer_response() -> tuple[str, dict]:
    import json

    return (
        json.dumps(
            {
                "summary": "FPT has a persisted composite score for research review.",
                "basis": "Based on the deterministic deep-symbol payload.",
                "risks_caveats": "Research-only context; freshness remains relevant.",
                "tool_trace_summary": "analysis.deep_symbol completed.",
                "missing_data": [],
                "grounded_source_refs": [],
                "research_metadata": {},
            }
        ),
        {"prompt_tokens": 10, "completion_tokens": 20},
    )


def test_app_deep_analysis_projects_evidence_end_to_end(conn, monkeypatch) -> None:
    from vnalpha.assistant.app import AssistantApp
    from vnalpha.assistant.gateway import FakeLLMClient

    _seed_analysis_artifacts(conn)

    def execute(_self, plan):
        step = next(s for s in plan.steps if s.tool_name == "analysis.deep_symbol")
        return {
            step.step_id: {
                "data": {
                    "tool": "analysis.deep_symbol",
                    "available": True,
                    "symbol": "FPT",
                    "as_of_date": "2026-07-13",
                    "candidate": {
                        "score": 0.82,
                        "candidate_class": "WATCH_CANDIDATE",
                        "setup_type": "ACCUMULATION_BASE",
                    },
                    "feature_context": {"close": 100.0, "ma20": 98.0},
                    "levels": {"support_20d": 95.0, "resistance_20d": 105.0},
                    "freshness": {"price_bar_date": "2026-07-13"},
                    "lineage": {"source": "persisted warehouse"},
                    "artifact_refs": ["candidate_score:FPT:2026-07-13"],
                    "missing_data": [],
                    "caveats": ["Research-only persisted context."],
                },
                "summary": "Persisted deep research context.",
                "warnings": [],
            }
        }

    monkeypatch.setattr("vnalpha.assistant.executor.AssistantExecutor.execute", execute)
    fake = FakeLLMClient(responses=[_intent_response(), _answer_response()])
    app = AssistantApp(conn, surface="test", llm_client=fake)

    answer, plan = app.ask("Phân tích FPT.", date="2026-07-13")

    assert plan.intent == "deep_analyze_symbol"
    projection = answer.research_metadata["knowledge_projection"]
    assert projection["symbol"] == "FPT"
    projected_predicates = {claim["predicate"] for claim in projection["projected"]}
    assert "composite_score" in projected_predicates

    claims = SymbolMemoryRepository(conn).list_claims("FPT")
    assert any(claim.predicate == "composite_score" for claim in claims)
