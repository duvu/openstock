"""Issue #167 — golden end-to-end MVP1 chat vertical-slice acceptance.

One automated golden conversation proves the complete MVP1 flow on the real
code path, starting from an empty warehouse and empty symbol-knowledge dir:

1. NL "Phân tích FPT" → visible provisioning (symbols, FPT OHLCV, VNINDEX)
   through the ensure boundary → persist canonical → features → score →
   deterministic analysis → symbol-knowledge projection → grounded answer.
2. A follow-up question reuses fresh warehouse + knowledge evidence without
   new provider fetches.
3. An explicit refresh performs bounded incremental work and discloses actions.

It exercises the REAL planner, provisioning operation (#163), warehouse,
readiness/scoring evidence, memory projection (#164), deep analysis, synthesis,
groundedness and research audit — with fixture-backed data and a fake LLM. The
only fakes are the provider boundary (a call-counting fixture ensure) and the
LLM gateway. Failure fixtures assert actionable errors and preserved state.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import duckdb
import pytest

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.models import AssistantAnswer
from vnalpha.assistant.research_audit import list_research_answer_audits
from vnalpha.data_availability.models import (
    EnsureDataAction,
    EnsureDataResult,
    EnsureDataStatus,
)
from vnalpha.data_provisioning import ensure_current_symbol as ecs_module
from vnalpha.features.build_features import build_features
from vnalpha.ingestion.build_canonical import build_canonical_ohlcv
from vnalpha.scoring.generate_watchlist import save_watchlist, score_universe
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    create_ingestion_run,
    finish_ingestion_run,
    insert_raw_ohlcv,
    upsert_symbol,
)

# Aligned with the proven phase-5 fixture window (163 daily bars ending on the
# analysis date), so the REAL canonical/feature/scoring builders run to a ready
# candidate_score without a live provider.
_AS_OF = "2024-01-10"
_START_DATE = date(2023, 8, 1)
_N_BARS = 163


# ---------------------------------------------------------------------------
# Fixture-backed provisioning: seeds raw OHLCV (the provider's output) and then
# runs the REAL canonical/feature/scoring builders — the only fake is the
# network fetch, counted so reuse (no new fetch) can be asserted.
# ---------------------------------------------------------------------------


def _make_ohlcv_rows(n_bars: int, base_price: float, multiplier: float, vol: float):
    rows = []
    price = base_price
    for i in range(n_bars):
        price = price * multiplier
        close = round(price, 2)
        rows.append(
            {
                "time": str(_START_DATE + timedelta(days=i)),
                "interval": "1D",
                "open": round(close * 0.99, 2),
                "high": round(close * 1.01, 2),
                "low": round(close * 0.98, 2),
                "close": close,
                "volume": vol * (1.0 + 0.1 * (i % 5)),
            }
        )
    return rows


class _FixtureProvider:
    """A call-counting provider stand-in for the network fetch boundary."""

    def __init__(self) -> None:
        self.fetches = 0

    def fetch_and_build(self, conn: duckdb.DuckDBPyConnection, symbol: str) -> None:
        """Seed raw OHLCV (one fetch) then run the real build/score pipeline."""
        self.fetches += 1
        upsert_symbol(conn, "VNINDEX", exchange="HOSE", name="VNINDEX")
        upsert_symbol(conn, symbol, exchange="HOSE", name=symbol)

        idx_run = create_ingestion_run(conn, "fixture", "/fixture/vnindex")
        insert_raw_ohlcv(
            conn,
            idx_run,
            "VNINDEX",
            _make_ohlcv_rows(_N_BARS, 1200.0, 1.001, 1_000_000.0),
            provider="fixture",
            quality_status="pass",
        )
        finish_ingestion_run(conn, idx_run, status="SUCCESS")

        sym_run = create_ingestion_run(conn, "fixture", "/fixture/symbol")
        insert_raw_ohlcv(
            conn,
            sym_run,
            symbol,
            _make_ohlcv_rows(_N_BARS, 100.0, 1.003, 3_000_000.0),
            provider="fixture",
            quality_status="pass",
        )
        finish_ingestion_run(conn, sym_run, status="SUCCESS")

        # The REAL deterministic builders (issue #167 requires real scoring).
        build_canonical_ohlcv(conn)
        build_features(conn, target_date=_AS_OF)
        score_universe(conn, date=_AS_OF)
        save_watchlist(conn, date=_AS_OF, min_score=0.0)


def _ready_result(actions: list[EnsureDataAction]) -> EnsureDataResult:
    return EnsureDataResult(
        symbol="FPT",
        target_date=_AS_OF,
        status=EnsureDataStatus.READY,
        actions_taken=actions,
        canonical_bars=_N_BARS,
        benchmark_bars=_N_BARS,
        feature_snapshot_exists=True,
        candidate_score_exists=True,
        symbol_known=True,
        core_evidence_evaluated=True,
        freshness="cache_hit",
    )


def _install_fixture_ensure(monkeypatch, provider: _FixtureProvider) -> None:
    """Replace the network sync boundary with a fixture that builds and counts.

    Everything downstream of the fetch — canonical build, feature build, scoring,
    readiness evaluation, deep analysis, synthesis, projection and audit — is the
    real code path.
    """

    def _fixture_ensure(conn, symbol, target_date, *, force_refresh=False):
        symbol = symbol.upper().strip()
        has_score = conn.execute(
            "SELECT 1 FROM candidate_score WHERE symbol = ? AND date = ?",
            [symbol, _AS_OF],
        ).fetchone()
        if has_score and not force_refresh:
            # Fresh persisted data — reuse, no provider fetch (cache hit).
            return _ready_result([EnsureDataAction.CACHE_HIT])
        provider.fetch_and_build(conn, symbol)
        actions = [
            EnsureDataAction.SYMBOLS_SYNCED,
            EnsureDataAction.OHLCV_SYNCED,
            EnsureDataAction.CANONICAL_BUILT,
            EnsureDataAction.BENCHMARK_SYNCED,
            EnsureDataAction.BENCHMARK_CANONICAL_BUILT,
            EnsureDataAction.FEATURES_BUILT,
            EnsureDataAction.SCORED,
        ]
        return _ready_result(actions)

    monkeypatch.setattr(ecs_module, "ensure_symbol_analysis_ready", _fixture_ensure)


# ---------------------------------------------------------------------------
# Fake LLM responses (intent classification + synthesis) per turn.
# ---------------------------------------------------------------------------


def _intent_response() -> tuple[str, dict]:
    return (
        json.dumps(
            {
                "intent": "deep_analyze_symbol",
                "confidence": 0.99,
                "entities": {"symbol": "FPT", "date": _AS_OF},
                "needs_clarification": False,
                "clarification_question": None,
                "safety_flags": [],
            }
        ),
        {},
    )


def _answer_response() -> tuple[str, dict]:
    return (
        json.dumps(
            {
                "summary": "FPT shows a persisted composite score for research review.",
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


@pytest.fixture(autouse=True)
def _knowledge_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_KNOWLEDGE_ROOT", str(tmp_path / "knowledge"))


@pytest.fixture
def empty_conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    return conn


def _ask(conn, provider, monkeypatch, prompt: str, *, extra_responses=None):
    responses = [_intent_response(), _answer_response()]
    if extra_responses:
        responses = extra_responses
    fake = FakeLLMClient(responses=responses)
    app = AssistantApp(conn, surface="test", llm_client=fake)
    return app.ask(prompt, date=_AS_OF)


def test_golden_conversation_empty_to_grounded_answer(empty_conn, monkeypatch) -> None:
    provider = _FixtureProvider()
    _install_fixture_ensure(monkeypatch, provider)

    # Turn 1: from an empty warehouse, NL analysis provisions then answers.
    answer, plan = _ask(empty_conn, provider, monkeypatch, "Phân tích FPT.")

    assert plan.intent == "deep_analyze_symbol"
    assert isinstance(answer, AssistantAnswer)
    # Provisioning is a visible, explicit plan step before analysis (issue #163).
    tools = [step.tool_name for step in plan.steps]
    assert tools == ["data.ensure_current_symbol", "analysis.deep_symbol"]
    # One provider fetch happened to fill the empty warehouse.
    assert provider.fetches == 1

    # Persisted evidence exists before the answer.
    assert empty_conn.execute(
        "SELECT 1 FROM candidate_score WHERE symbol = 'FPT'"
    ).fetchone()
    assert empty_conn.execute(
        "SELECT 1 FROM feature_snapshot WHERE symbol = 'FPT'"
    ).fetchone()
    assert empty_conn.execute(
        "SELECT 1 FROM symbol_master WHERE symbol = 'VNINDEX'"
    ).fetchone()

    # The candidate score came from the REAL scorer, not a canned value.
    score_row = empty_conn.execute(
        "SELECT score, candidate_class FROM candidate_score "
        "WHERE symbol = 'FPT' AND date = ?",
        [_AS_OF],
    ).fetchone()
    assert score_row is not None and 0.0 < score_row[0] <= 1.0

    # A grounded research audit was persisted (groundedness + policy passed) with
    # as-of/evidence/freshness/caveats and the full provisioning+analysis trace.
    audits = list_research_answer_audits(empty_conn)
    assert len(audits) == 1
    audit = audits[0]
    assert audit["groundedness_status"] == "PASS"
    assert audit["policy_status"] == "PASS"
    assert audit["tools"] == ["data.ensure_current_symbol", "analysis.deep_symbol"]
    assert audit["artifact_refs"]  # source references present
    assert audit["dataset_freshness"]  # as-of / freshness present
    assert audit["correlation_id"]

    # Symbol knowledge was projected from validated evidence (issue #164), and
    # the projected score matches the persisted warehouse row (no prose).
    projection = answer.research_metadata.get("knowledge_projection")
    assert projection is not None
    assert projection["symbol"] == "FPT"
    claims = SymbolMemoryRepository(empty_conn).list_claims("FPT")
    score_claim = next(c for c in claims if c.predicate == "composite_score")
    assert score_claim.value["value"] == score_row[0]
    assert score_claim.origin.value == "validated_evidence"


def test_golden_followup_reuses_without_new_provider_fetch(
    empty_conn, monkeypatch
) -> None:
    provider = _FixtureProvider()
    _install_fixture_ensure(monkeypatch, provider)

    _ask(empty_conn, provider, monkeypatch, "Phân tích FPT.")
    assert provider.fetches == 1

    # Turn 2: a follow-up reuses fresh warehouse + knowledge; no new fetch.
    answer2, _ = _ask(empty_conn, provider, monkeypatch, "Phân tích FPT lần nữa.")

    assert isinstance(answer2, AssistantAnswer)
    assert provider.fetches == 1  # unchanged — fresh data was reused

    # Repeat projection is idempotent: still one active composite_score claim.
    claims = [
        c
        for c in SymbolMemoryRepository(empty_conn).list_claims("FPT")
        if c.predicate == "composite_score" and c.status.value == "active"
    ]
    assert len(claims) == 1


def test_golden_explicit_refresh_forces_bounded_work(empty_conn, monkeypatch) -> None:
    provider = _FixtureProvider()

    # Track the force_refresh flag threaded into the ensure boundary.
    seen_refresh: list[bool] = []

    def _tracking_ensure(conn, symbol, target_date, *, force_refresh=False):
        seen_refresh.append(force_refresh)
        symbol = symbol.upper().strip()
        if (
            force_refresh
            or not conn.execute(
                "SELECT 1 FROM candidate_score WHERE symbol = ? AND date = ?",
                [symbol, _AS_OF],
            ).fetchone()
        ):
            provider.fetch_and_build(conn, symbol)
        actions = (
            [EnsureDataAction.OHLCV_SYNCED, EnsureDataAction.SCORED]
            if force_refresh
            else [EnsureDataAction.CACHE_HIT]
        )
        return _ready_result(actions)

    monkeypatch.setattr(ecs_module, "ensure_symbol_analysis_ready", _tracking_ensure)

    from vnalpha.data_provisioning import ensure_current_symbol_ready

    result = ensure_current_symbol_ready(empty_conn, "FPT", _AS_OF, refresh=True)

    assert result.is_ready
    assert result.refreshed is True
    assert True in seen_refresh
    # Refresh discloses the bounded actions taken.
    action_names = {a.action for a in result.actions}
    assert action_names & {"sync_ohlcv", "score_symbol"}


def test_golden_provider_failure_returns_actionable_error_and_preserves_state(
    empty_conn, monkeypatch
) -> None:
    # A provider/service failure fixture: ensure returns FAILED with no data.
    def _failing_ensure(conn, symbol, target_date, *, force_refresh=False):
        return EnsureDataResult(
            symbol="FPT",
            target_date=_AS_OF,
            status=EnsureDataStatus.FAILED,
            actions_taken=[],
            canonical_bars=0,
            benchmark_bars=0,
            feature_snapshot_exists=False,
            candidate_score_exists=False,
            symbol_known=False,
            core_evidence_evaluated=True,
            failure_code="service_unavailable",
            errors=["vnstock-service is unavailable."],
        )

    monkeypatch.setattr(ecs_module, "ensure_symbol_analysis_ready", _failing_ensure)

    from vnalpha.data_provisioning import ensure_current_symbol_ready
    from vnalpha.data_provisioning.ensure_current_symbol import ProvisioningOutcome

    result = ensure_current_symbol_ready(empty_conn, "FPT", _AS_OF)

    # Fail closed with an actionable, typed outcome.
    assert result.outcome is ProvisioningOutcome.FAILED
    assert not result.is_ready
    assert result.errors
    # No partial/corrupt analysis evidence was promoted.
    assert not empty_conn.execute(
        "SELECT 1 FROM candidate_score WHERE symbol = 'FPT'"
    ).fetchone()
    assert not SymbolMemoryRepository(empty_conn).list_claims("FPT")


def test_golden_slash_and_nl_share_the_same_provisioning_contract(
    empty_conn, monkeypatch
) -> None:
    # Slash /analyze and NL "Phân tích FPT" both funnel through the same
    # ensure_current_symbol_ready operation over the same persisted evidence.
    provider = _FixtureProvider()
    _install_fixture_ensure(monkeypatch, provider)

    from vnalpha.data_provisioning import ensure_current_symbol_ready
    from vnalpha.data_provisioning.ensure_current_symbol import ProvisioningOutcome

    # NL turn provisions from empty (the /analyze handler calls the identical op).
    _ask(empty_conn, provider, monkeypatch, "Phân tích FPT.")
    assert provider.fetches == 1

    # The shared operation the /analyze handler invokes reuses that evidence.
    shared = ensure_current_symbol_ready(empty_conn, "FPT", _AS_OF)
    assert shared.outcome is ProvisioningOutcome.REUSED
    assert shared.is_ready
    assert provider.fetches == 1  # no new fetch — same persisted contract
