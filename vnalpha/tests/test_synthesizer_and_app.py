"""Tests for Phase 5.9 AnswerSynthesizer and AssistantApp orchestrator."""

from __future__ import annotations

import json

import duckdb
import pytest

from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    ToolPlanStep,
)
from vnalpha.assistant.synthesizer import (
    AnswerSynthesizer,
)
from vnalpha.warehouse.migrations import run_migrations

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_INTENT_JSON = '{"intent": "scan_candidates", "confidence": 0.9, "entities": {}}'
VALID_SYNTHESIS_JSON = json.dumps(
    {
        "summary": "3 strong candidates found.",
        "basis": "Based on persisted score.",
        "risks_caveats": "See risk flags.",
        "tool_trace_summary": "Ran watchlist.scan.",
        "missing_data": [],
    }
)


def _make_fake_llm() -> FakeLLMClient:
    """FakeLLMClient: first call = intent classify, second call = synthesis."""
    return FakeLLMClient(
        responses=[
            (VALID_INTENT_JSON, {}),
            (VALID_SYNTHESIS_JSON, {}),
        ]
    )


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


@pytest.fixture
def fake_llm():
    return _make_fake_llm()


@pytest.fixture
def synthesizer(fake_llm):
    return AnswerSynthesizer(fake_llm)


def _make_scan_plan() -> AssistantPlan:
    return AssistantPlan(
        intent="scan_candidates",
        steps=[
            ToolPlanStep(
                step_id="step_1",
                tool_name="watchlist.scan",
                arguments={"date": "2026-07-01"},
                purpose="Retrieve ranked research candidates",
                required_permission="READ_WATCHLIST",
            )
        ],
        required_artifacts=["daily_watchlist", "candidate_score"],
    )


# ===========================================================================
# Synthesizer tests
# ===========================================================================


class TestAnswerSynthesizer:
    def test_synthesizer_returns_answer_with_summary(self):
        """Synthesizer returns an AssistantAnswer with non-empty summary."""
        client = FakeLLMClient(responses=[(VALID_SYNTHESIS_JSON, {})])
        synth = AnswerSynthesizer(client)
        plan = _make_scan_plan()
        tool_outputs = {"step_1": {"candidates": [{"symbol": "FPT", "score": 0.85}]}}
        answer = synth.synthesize("Show me today's candidates", plan, tool_outputs)
        assert isinstance(answer, AssistantAnswer)
        assert answer.summary == "3 strong candidates found."
        assert answer.basis == "Based on persisted score."
        assert answer.risks_caveats == "See risk flags."
        assert answer.tool_trace_summary == "Ran watchlist.scan."


# ===========================================================================
# AssistantApp tests
# ===========================================================================
