"""Tests for Phase 5.9 AnswerSynthesizer and AssistantApp orchestrator."""

from __future__ import annotations

import json

import duckdb
import pytest

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.errors import SynthesisError
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    RefusalMessage,
    ToolPlanStep,
)
from vnalpha.assistant.response_parser import (
    parse_synthesis_response as _parse_synthesis_response,
)
from vnalpha.assistant.synthesizer import (
    MISSING_DATA_TEMPLATES,
    SYNTHESIZER_SYSTEM_PROMPT,
    AnswerSynthesizer,
    _build_synthesis_messages,
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

    def test_synthesizer_preserves_raw_tool_outputs_empty(self):
        """raw_tool_outputs defaults to empty dict when not in LLM response."""
        client = FakeLLMClient(responses=[(VALID_SYNTHESIS_JSON, {})])
        synth = AnswerSynthesizer(client)
        plan = _make_scan_plan()
        answer = synth.synthesize("question", plan, {})
        # VALID_SYNTHESIS_JSON has no raw_tool_outputs field → defaults to {}
        assert answer.raw_tool_outputs == {}

    def test_synthesizer_invalid_json_raises_synthesis_error(self):
        """Non-JSON response from LLM raises SynthesisError."""
        client = FakeLLMClient(responses=[("not valid json at all!!!", {})])
        synth = AnswerSynthesizer(client)
        plan = _make_scan_plan()
        with pytest.raises(SynthesisError, match="Invalid JSON from synthesizer"):
            synth.synthesize("question", plan, {})

    def test_synthesizer_missing_data_populated(self):
        """missing_data list is correctly parsed from LLM response."""
        response = json.dumps(
            {
                "summary": "FPT score missing.",
                "basis": "No score found.",
                "risks_caveats": "N/A",
                "tool_trace_summary": "Ran watchlist.scan.",
                "missing_data": ["no_candidate_score for FPT on 2026-07-01"],
            }
        )
        client = FakeLLMClient(responses=[(response, {})])
        synth = AnswerSynthesizer(client)
        plan = _make_scan_plan()
        answer = synth.synthesize("Explain FPT", plan, {})
        assert len(answer.missing_data) == 1
        assert "FPT" in answer.missing_data[0]

    def test_synthesizer_grounding_check(self):
        """SYNTHESIZER_SYSTEM_PROMPT must contain the override prohibition."""
        assert "MUST NOT override" in SYNTHESIZER_SYSTEM_PROMPT

    def test_context_synthesis_prompt_requires_caveat_first_persisted_disclosure(self):
        rules = SYNTHESIZER_SYSTEM_PROMPT.lower()

        assert "persisted research context" in rules
        assert "methodology" in rules
        assert "freshness" in rules
        assert "quality" in rules
        assert "caveat" in rules
        assert "missing" in rules
        assert "action guidance" in rules

    def test_context_synthesis_message_includes_required_artifacts(self):
        plan = AssistantPlan(
            intent="review_market_regime",
            steps=[],
            required_artifacts=["market_regime_snapshot"],
        )

        messages = _build_synthesis_messages("Review regime", plan, {})

        payload = json.loads(messages[1]["content"])
        assert payload["required_artifacts"] == ["market_regime_snapshot"]

    @pytest.mark.parametrize(
        "summary",
        ["Buy FPT now.", "Rebalance the position.", "Open a long position."],
    )
    def test_context_synthesis_rejects_action_language(self, summary: str):
        response = json.dumps(
            {
                "summary": summary,
                "basis": "Persisted context.",
                "risks_caveats": "Caveat: incomplete data.",
                "tool_trace_summary": "market.get_regime executed.",
                "missing_data": [],
            }
        )
        plan = AssistantPlan(intent="review_market_regime", steps=[])

        with pytest.raises(SynthesisError, match="research-only"):
            AnswerSynthesizer(FakeLLMClient(responses=[(response, {})])).synthesize(
                "Review regime", plan, {"step_1": {"snapshot": None}}
            )

    def test_complete_sector_collection_accepts_descriptive_summary(self):
        response = json.dumps(
            {
                "summary": "Technology leads context.",
                "basis": "Persisted.",
                "risks_caveats": "None.",
                "tool_trace_summary": "sector.get_strength",
                "missing_data": [],
            }
        )
        answer = AnswerSynthesizer(
            FakeLLMClient(responses=[(response, {})])
        ).synthesize(
            "Review sectors",
            AssistantPlan(intent="review_sector_strength", steps=[]),
            {
                "step_1": {
                    "data": {
                        "snapshots": [{"sector": "Technology"}],
                        "quality": "COMPLETE",
                        "caveats": [],
                    }
                }
            },
        )
        assert answer.summary.startswith("Technology")

    def test_context_synthesis_rejects_missing_snapshot_without_caveat_first_summary(
        self,
    ):
        response = json.dumps(
            {
                "summary": "The market regime is mixed.",
                "basis": "Persisted context.",
                "risks_caveats": "No snapshot is available.",
                "tool_trace_summary": "market.get_regime executed.",
                "missing_data": [],
            }
        )
        plan = AssistantPlan(intent="review_market_regime", steps=[])

        with pytest.raises(SynthesisError, match="caveat-first"):
            AnswerSynthesizer(FakeLLMClient(responses=[(response, {})])).synthesize(
                "Review regime", plan, {"step_1": {"snapshot": None}}
            )

    def test_missing_data_templates_exist(self):
        """MISSING_DATA_TEMPLATES must contain the required keys."""
        required_keys = {
            "no_candidate_score",
            "no_feature_snapshot",
            "no_canonical_ohlcv",
            "no_watchlist",
            "generic",
        }
        assert required_keys.issubset(set(MISSING_DATA_TEMPLATES.keys()))

    def test_synthesizer_llm_failure_raises_synthesis_error(self):
        """If LLM chat raises, SynthesisError is raised."""

        class BrokenLLM:
            def chat(self, messages, response_schema=None, *, stage="unknown"):
                raise RuntimeError("network down")

        synth = AnswerSynthesizer(BrokenLLM())
        plan = _make_scan_plan()
        with pytest.raises(SynthesisError, match="LLM synthesis call failed"):
            synth.synthesize("question", plan, {})

    def test_build_synthesis_messages_structure(self):
        """_build_synthesis_messages includes system + user roles."""
        plan = _make_scan_plan()
        msgs = _build_synthesis_messages("my question", plan, {"step_1": {"x": 1}})
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        user_payload = json.loads(msgs[1]["content"])
        assert user_payload["user_question"] == "my question"
        assert user_payload["intent"] == "scan_candidates"
        assert "tool_outputs" in user_payload

    def test_parse_synthesis_response_defaults(self):
        """_parse_synthesis_response handles partial JSON gracefully."""
        answer = _parse_synthesis_response('{"summary": "hello"}')
        assert answer.summary == "hello"
        assert answer.basis == ""
        assert answer.missing_data == []


# ===========================================================================
# AssistantApp tests
# ===========================================================================


class TestAssistantApp:
    def test_app_ask_returns_answer_and_plan(self, conn):
        """Happy path: FakeLLM returns valid intent + synthesis JSON → AssistantAnswer."""
        app = AssistantApp(conn, llm_client=_make_fake_llm())
        answer, plan = app.ask("Show me today's research candidates", date="2026-07-01")
        assert isinstance(answer, AssistantAnswer)
        assert answer.summary == "3 strong candidates found."
        assert plan.intent == "scan_candidates"

    def test_app_ask_refused_by_policy(self, conn):
        """Prompt 'Buy FPT now' triggers policy refusal → RefusalMessage returned."""
        app = AssistantApp(conn, llm_client=_make_fake_llm())
        result, plan = app.ask("Buy FPT now")
        assert isinstance(result, RefusalMessage)
        assert result.policy_category == "TRADING_EXECUTION"
        assert plan.intent == "unsupported_or_unsafe"

    def test_app_ask_no_execute_returns_plan_preview(self, conn):
        """no_execute=True skips tool execution; summary contains '[Plan preview'."""
        app = AssistantApp(conn, llm_client=_make_fake_llm())
        answer, plan = app.ask(
            "Show me research candidates", date="2026-07-01", no_execute=True
        )
        assert isinstance(answer, AssistantAnswer)
        assert "[Plan preview" in answer.summary
        assert answer.tool_trace_summary == "No tools executed (--no-execute mode)."

    def test_app_ask_persists_session(self, conn):
        """After ask, assistant_session table has a row with non-RUNNING status."""
        app = AssistantApp(conn, llm_client=_make_fake_llm())
        app.ask("Show me research candidates", date="2026-07-01")
        rows = conn.execute("SELECT status FROM assistant_session").fetchall()
        assert len(rows) >= 1
        statuses = {r[0] for r in rows}
        # Should be SUCCESS or REFUSED, not stuck at RUNNING
        assert statuses & {"SUCCESS", "REFUSED"}

    def test_app_ask_persists_llm_trace(self, conn):
        """After a successful ask, llm_trace table has at least one row."""
        app = AssistantApp(conn, llm_client=_make_fake_llm())
        app.ask("Show me research candidates", date="2026-07-01")
        rows = conn.execute("SELECT COUNT(*) FROM llm_trace").fetchone()
        assert rows[0] >= 1

    def test_app_ask_date_injected_into_entities(self, conn):
        """date kwarg is injected into plan step arguments."""
        app = AssistantApp(conn, llm_client=_make_fake_llm())
        answer, plan = app.ask("Show me candidates", date="2026-07-01")
        # Plan has at least one step; date should appear in step arguments
        assert len(plan.steps) >= 1
        all_args = [step.arguments for step in plan.steps]
        assert any("date" in args for args in all_args)

    def test_app_ask_unsupported_intent_refused(self, conn):
        """LLM returning unsupported_or_unsafe intent results in RefusalMessage."""
        unsafe_json = '{"intent": "unsupported_or_unsafe", "confidence": 0.99, "entities": {}, "safety_flags": ["UNSUPPORTED"]}'
        fake = FakeLLMClient(responses=[(unsafe_json, {}), (VALID_SYNTHESIS_JSON, {})])
        app = AssistantApp(conn, llm_client=fake)
        result, plan = app.ask("Do something weird")
        assert isinstance(result, RefusalMessage)
        assert plan.is_refusal()

    def test_app_refusal_session_status_refused(self, conn):
        """After a policy refusal, session status is REFUSED in DB."""
        app = AssistantApp(conn, llm_client=_make_fake_llm())
        app.ask("Buy FPT now")
        rows = conn.execute(
            "SELECT status FROM assistant_session WHERE status = 'REFUSED'"
        ).fetchall()
        assert len(rows) >= 1

    def test_app_no_execute_session_status_success(self, conn):
        """no_execute=True still results in SUCCESS session status."""
        app = AssistantApp(conn, llm_client=_make_fake_llm())
        app.ask("Show me candidates", date="2026-07-01", no_execute=True)
        rows = conn.execute(
            "SELECT status FROM assistant_session WHERE status = 'SUCCESS'"
        ).fetchall()
        assert len(rows) >= 1

    def test_app_scan_plan_has_watchlist_tool(self, conn):
        """scan_candidates intent produces a plan with watchlist.scan step."""
        app = AssistantApp(conn, llm_client=_make_fake_llm())
        _answer, plan = app.ask("Show me candidates", date="2026-07-01")
        tool_names = [step.tool_name for step in plan.steps]
        assert "watchlist.scan" in tool_names

    def test_app_ask_classify_trace_persisted(self, conn):
        """classify stage llm_trace row is stored with SUCCESS status after ask."""
        app = AssistantApp(conn, llm_client=_make_fake_llm())
        app.ask("Show me candidates", date="2026-07-01")
        rows = conn.execute(
            "SELECT stage, status FROM llm_trace WHERE stage = 'classify'"
        ).fetchall()
        assert len(rows) >= 1
        assert rows[0][1] == "SUCCESS"

    def test_app_ask_synthesize_trace_persisted(self, conn):
        """synthesize stage llm_trace row is stored with SUCCESS status after ask."""
        app = AssistantApp(conn, llm_client=_make_fake_llm())
        app.ask("Show me candidates", date="2026-07-01")
        rows = conn.execute(
            "SELECT stage, status FROM llm_trace WHERE stage = 'synthesize'"
        ).fetchall()
        assert len(rows) >= 1
        assert rows[0][1] == "SUCCESS"

    def test_app_no_execute_no_synthesize_trace(self, conn):
        """no_execute=True skips synthesize LLM call → no synthesize llm_trace row."""
        app = AssistantApp(conn, llm_client=_make_fake_llm())
        app.ask("Show me candidates", date="2026-07-01", no_execute=True)
        rows = conn.execute(
            "SELECT COUNT(*) FROM llm_trace WHERE stage = 'synthesize'"
        ).fetchone()
        assert rows[0] == 0

    def test_app_surface_stored_in_session(self, conn):
        """surface kwarg is persisted in assistant_session table."""
        app = AssistantApp(conn, surface="web", llm_client=_make_fake_llm())
        app.ask("Show me candidates", date="2026-07-01")
        rows = conn.execute(
            "SELECT surface FROM assistant_session WHERE surface = 'web'"
        ).fetchall()
        assert len(rows) >= 1

    def test_app_ask_answer_json_persisted(self, conn):
        """After successful ask, answer_json in assistant_session is non-null."""
        app = AssistantApp(conn, llm_client=_make_fake_llm())
        app.ask("Show me candidates", date="2026-07-01")
        rows = conn.execute(
            "SELECT answer_json FROM assistant_session WHERE status = 'SUCCESS'"
        ).fetchall()
        assert len(rows) >= 1
        answer_json = rows[0][0]
        assert answer_json is not None
        data = json.loads(answer_json)
        assert "summary" in data

    def test_app_ask_plan_json_persisted(self, conn):
        """After successful ask, plan_json in assistant_session is non-null."""
        app = AssistantApp(conn, llm_client=_make_fake_llm())
        app.ask("Show me candidates", date="2026-07-01")
        rows = conn.execute(
            "SELECT plan_json FROM assistant_session WHERE status = 'SUCCESS'"
        ).fetchall()
        assert len(rows) >= 1
        plan_json = rows[0][0]
        assert plan_json is not None
        data = json.loads(plan_json)
        assert "intent" in data
