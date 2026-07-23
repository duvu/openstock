"""Tests for Phase 5.9 AnswerSynthesizer and AssistantApp orchestrator."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import duckdb
import pytest

from vnalpha.assistant.connection_runtime import AssistantApp
from vnalpha.assistant.degraded_answer import (
    AssistantDegradation,
    AssistantFailureStage,
    build_deterministic_tool_answer,
    degradation_warning,
    lifecycle_warning,
)
from vnalpha.assistant.errors import AssistantLifecycleError, SynthesisError
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    AssistantRequest,
    ToolPlanStep,
)
from vnalpha.assistant.response_json import parse_synthesis_response
from vnalpha.assistant.synthesizer import (
    AnswerSynthesizer,
)
from vnalpha.chat.context import ChatContext
from vnalpha.research_intelligence.models import MarketRegimeSnapshot
from vnalpha.tui.screens.assistant import render_assistant_answer
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import upsert_market_regime_snapshot

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


def _market_plan() -> AssistantPlan:
    return AssistantPlan(
        intent="review_market_regime",
        steps=[
            ToolPlanStep(
                step_id="step_1",
                tool_name="market.get_regime",
                arguments={"date": "2026-07-01"},
                purpose="Review persisted market regime research context",
                required_permission="READ_FEATURES",
            )
        ],
        required_artifacts=["market_regime_snapshot"],
    )


def _market_tool_output(*, summary: str = "Persisted market regime: CONSTRUCTIVE."):
    return {
        "step_1": {
            "summary": summary,
            "warnings": ["Persisted context may be stale."],
            "data": {
                "snapshot": {"regime": "CONSTRUCTIVE"},
                "freshness": {"status": "CURRENT"},
                "lineage": {"source": "warehouse"},
                "quality": "COMPLETE",
                "caveats": ["Persisted context may be stale."],
                "artifact_refs": ["fixture://market-regime"],
            },
        }
    }


def _market_snapshot(as_of_date: date) -> MarketRegimeSnapshot:
    return MarketRegimeSnapshot(
        as_of_date=as_of_date,
        benchmark_symbol="VNINDEX",
        benchmark_bar_date=as_of_date,
        close=1300.0,
        ma20=1280.0,
        ma50=1250.0,
        ma50_slope=2.0,
        return20=0.03,
        return60=0.08,
        volatility20=0.12,
        breadth_active_count=100,
        breadth_eligible_count=90,
        breadth_excluded_count=10,
        breadth_coverage=0.9,
        pct_above_ma20=0.6,
        pct_above_ma50=0.55,
        pct_positive_return20=0.58,
        regime="CONSTRUCTIVE",
        trend="UPTREND",
        volatility="NORMAL",
        quality="COMPLETE",
        caveats=("Persisted context may be stale.",),
        lineage={"source": "fixture"},
        methodology_version="test-v1",
        generated_at=datetime.now(timezone.utc),
    )


# ===========================================================================
# Synthesizer tests
# ===========================================================================


class TestAnswerSynthesizer:
    def test_synthesizer_preserves_read_only_results_when_degraded(
        self, conn, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("VNALPHA_BUILD_SHA", "0123456789abcdef")
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

        class GatewayUnavailable:
            last_raw_responses: tuple[dict, ...] = ()

            def chat(self, *_args, **_kwargs):
                raise RuntimeError("gateway unavailable")

        fallback = AnswerSynthesizer(GatewayUnavailable()).synthesize(
            "Show me today's candidates",
            plan,
            tool_outputs,
        )
        assert fallback.research_metadata["synthesis_status"] == "FALLBACK_SUCCESS"
        assert fallback.research_metadata["degradation"]["stage"] == "SYNTHESIS_CALL"
        assert "AI synthesis unavailable" in fallback.risks_caveats

        untrusted_fallback = build_deterministic_tool_answer(
            plan,
            tool_outputs,
            AssistantDegradation(
                AssistantFailureStage.SYNTHESIS_CALL,
                "GATEWAY_FAILURE",
                warning="ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd",
            ),
        )
        assert untrusted_fallback is not None
        assert "ghp_" not in untrusted_fallback.risks_caveats
        assert "ghp_" not in untrusted_fallback.research_metadata["degradation"]
        assert "ghp_" not in untrusted_fallback.research_metadata["fallback_reason"]
        assert (
            parse_synthesis_response(
                json.dumps(
                    {
                        "research_metadata": {"warning": "ghp_secret"},
                        "raw_tool_outputs": {"warning": "ghp_secret"},
                    }
                )
            ).research_metadata
            == {}
        )
        assert (
            parse_synthesis_response(
                json.dumps({"raw_tool_outputs": {"warning": "ghp_secret"}})
            ).raw_tool_outputs
            == {}
        )

        assert (
            build_deterministic_tool_answer(
                AssistantPlan(intent="scan_candidates", steps=[]),
                {"step_1": {"summary": "available"}},
                AssistantDegradation(
                    AssistantFailureStage.SYNTHESIS_CALL, "GATEWAY_FAILURE"
                ),
            )
            is None
        )
        assert (
            build_deterministic_tool_answer(
                AssistantPlan(
                    intent="scan_candidates",
                    steps=[],
                    refusal_reason="unsafe request",
                ),
                {"step_1": {"summary": "available"}},
                AssistantDegradation(
                    AssistantFailureStage.SYNTHESIS_CALL, "GATEWAY_FAILURE"
                ),
            )
            is None
        )
        assert (
            build_deterministic_tool_answer(
                plan,
                {"unrelated": {"summary": "available"}},
                AssistantDegradation(
                    AssistantFailureStage.SYNTHESIS_CALL, "GATEWAY_FAILURE"
                ),
            )
            is None
        )
        assert (
            build_deterministic_tool_answer(
                plan,
                {"step_1": None},
                AssistantDegradation(
                    AssistantFailureStage.SYNTHESIS_CALL, "GATEWAY_FAILURE"
                ),
            )
            is None
        )

        malformed = AnswerSynthesizer(
            FakeLLMClient(responses=[("{not-json", {})])
        ).synthesize(
            "Show me today's candidates",
            plan,
            tool_outputs,
        )
        assert malformed.research_metadata["degradation"]["stage"] == "SYNTHESIS_PARSE"

        market_plan = _market_plan()
        market_output = _market_tool_output()
        context_rejected = AnswerSynthesizer(
            FakeLLMClient(
                responses=[
                    (
                        json.dumps(
                            {
                                "summary": "Caveat: buy now.",
                                "basis": "Persisted market context.",
                                "risks_caveats": "Research only.",
                                "tool_trace_summary": "market.get_regime completed.",
                                "missing_data": [],
                            }
                        ),
                        {},
                    )
                ]
            )
        ).synthesize("thi truong hom nay", market_plan, market_output)
        assert context_rejected.research_metadata["degradation"]["category"] == (
            "CONTEXT_POLICY_REJECTED"
        )

        execution_disclaimer = AnswerSynthesizer(
            FakeLLMClient(
                responses=[
                    (
                        json.dumps(
                            {
                                "summary": "Caveat: this is not a buy or sell signal.",
                                "basis": "Persisted market context.",
                                "risks_caveats": "Research only.",
                                "tool_trace_summary": "market.get_regime completed.",
                                "missing_data": [],
                                "grounded_source_refs": [
                                    "tool:market.get_regime:step_1"
                                ],
                            }
                        ),
                        {},
                    )
                ]
            )
        ).synthesize("thi truong hom nay", market_plan, market_output)
        assert execution_disclaimer.research_metadata["fallback_used"] is False

        groundedness_rejected = AnswerSynthesizer(
            FakeLLMClient(
                responses=[
                    (
                        json.dumps(
                            {
                                "summary": "Caveat: persisted regime score is 99.",
                                "basis": "Persisted market context.",
                                "risks_caveats": "Research only.",
                                "tool_trace_summary": "market.get_regime completed.",
                                "missing_data": [],
                                "grounded_source_refs": [
                                    "tool:market.get_regime:step_1"
                                ],
                            }
                        ),
                        {},
                    )
                ]
            )
        ).synthesize("thi truong hom nay", market_plan, market_output)
        assert groundedness_rejected.research_metadata["degradation"]["category"] == (
            "GROUNDEDNESS_OR_POLICY_REJECTED"
        )

        with pytest.raises(SynthesisError, match="failed closed"):
            AnswerSynthesizer(GatewayUnavailable()).synthesize(
                "thi truong hom nay",
                market_plan,
                _market_tool_output(summary="buy now"),
            )

        class FailingSynthesisGateway:
            last_raw_responses: tuple[dict, ...] = ()

            def chat(self, _messages, *, stage, **_kwargs):
                if stage == "synthesize":
                    raise RuntimeError("gateway unavailable")
                return (
                    '{"intent":"review_market_regime","confidence":0.9,"entities":{}}',
                    {},
                )

        upsert_market_regime_snapshot(conn, _market_snapshot(date(2026, 7, 1)))
        result, executed_plan = AssistantApp(
            conn, llm_client=FailingSynthesisGateway()
        ).ask("thi truong hom nay", date="2026-07-01")
        assert isinstance(result, AssistantAnswer)
        assert executed_plan.steps[0].tool_name == "market.get_regime"
        assert (
            result.summary
            == "Caveat: persisted context includes limitations. Persisted market regime: CONSTRUCTIVE."
        )
        assert result.research_metadata["synthesis_status"] == "DEGRADED_SUCCESS"
        assert result.research_metadata["degradation"]["stage"] == "SYNTHESIS_CALL"
        assert result.research_metadata["degradation"]["trace_id"]
        assert result.research_metadata["degradation"]["model_route"] == ("client")
        assert result.research_metadata["degradation"]["build_sha"] == (
            "0123456789abcdef"
        )
        warning = degradation_warning(result)
        assert warning is not None
        assert "stage=SYNTHESIS_CALL" in warning
        assert "category=GATEWAY_FAILURE" in warning
        assert "correlation_id=" in warning
        assert "trace_id=" in warning
        assert "model_route=client" in warning
        assert "build_sha=0123456789abcdef" in warning
        rendered_tui_answer = render_assistant_answer(result).plain
        assert "Warning: AI synthesis unavailable" in rendered_tui_answer
        assert "stage=SYNTHESIS_CALL" in rendered_tui_answer
        assert conn.execute(
            "SELECT status FROM assistant_session ORDER BY started_at DESC LIMIT 1"
        ).fetchone() == ("DEGRADED_SUCCESS",)

        class ValidSynthesisGateway:
            last_raw_responses: tuple[dict, ...] = ()

            def chat(self, _messages, *, stage, **_kwargs):
                if stage == "synthesize":
                    return (
                        json.dumps(
                            {
                                "summary": "Caveat: persisted market context.",
                                "basis": "Persisted market regime evidence.",
                                "risks_caveats": "Research only; context may be stale.",
                                "tool_trace_summary": "market.get_regime completed.",
                                "missing_data": [],
                                "grounded_source_refs": [
                                    "tool:market.get_regime:step_1"
                                ],
                            }
                        ),
                        {"total_tokens": 7},
                    )
                return (
                    '{"intent":"review_market_regime","confidence":0.9,"entities":{}}',
                    {},
                )

        def persist_failure(**_kwargs):
            raise RuntimeError("audit unavailable")

        audit_app = AssistantApp(conn, llm_client=ValidSynthesisGateway())
        monkeypatch.setattr(audit_app, "_persist_research_audit", persist_failure)
        audit_result, _ = audit_app.ask("thi truong hom nay", date="2026-07-01")
        assert isinstance(audit_result, AssistantAnswer)
        assert audit_result.research_metadata["degradation"]["stage"] == "AUDIT_PERSIST"
        audit_trace_id = audit_result.research_metadata["degradation"]["trace_id"]
        audit_trace = conn.execute(
            "SELECT output_summary_json, usage_json FROM llm_trace WHERE llm_trace_id = ?",
            [audit_trace_id],
        ).fetchone()
        assert audit_trace is not None
        assert json.loads(audit_trace[0])["summary_length"] > 0
        assert json.loads(audit_trace[1])["total_tokens"] == 7

        projection_app = AssistantApp(conn, llm_client=ValidSynthesisGateway())
        monkeypatch.setattr(
            projection_app, "_project_analysis_evidence", lambda *_args: False
        )
        projection_result, _ = projection_app.ask(
            "thi truong hom nay", date="2026-07-01"
        )
        assert isinstance(projection_result, AssistantAnswer)
        assert projection_result.research_metadata["degradation"]["stage"] == (
            "KNOWLEDGE_PROJECTION"
        )

        def trace_failure(*_args, **_kwargs):
            raise RuntimeError("trace unavailable")

        with monkeypatch.context() as trace_patch:
            trace_patch.setattr(
                "vnalpha.assistant.connected_execute.finish_llm_trace",
                trace_failure,
            )
            trace_result, _ = AssistantApp(
                conn, llm_client=ValidSynthesisGateway()
            ).ask("thi truong hom nay", date="2026-07-01")
        assert isinstance(trace_result, AssistantAnswer)
        assert trace_result.research_metadata["degradation"]["stage"] == (
            "AUDIT_PERSIST"
        )

        with monkeypatch.context() as trace_patch:
            trace_patch.setattr(
                "vnalpha.assistant.connected_execute.create_llm_trace",
                trace_failure,
            )
            trace_creation_result, _ = AssistantApp(
                conn, llm_client=ValidSynthesisGateway()
            ).ask("thi truong hom nay", date="2026-07-01")
        assert isinstance(trace_creation_result, AssistantAnswer)
        assert trace_creation_result.research_metadata["degradation"]["category"] == (
            "SYNTHESIS_TRACE_CREATE_FAILURE"
        )

        monkeypatch.setenv("VNALPHA_BUILD_SHA", "api_key=build-secret")
        lifecycle = lifecycle_warning(
            AssistantFailureStage.CLASSIFY,
            "CLASSIFICATION_FAILURE",
            "0123456789abcdef",
        )
        assert "stage=CLASSIFY" in lifecycle
        assert "category=CLASSIFICATION_FAILURE" in lifecycle
        assert "cause=LIFECYCLE_FAILURE" in lifecycle
        assert "correlation_id=0123456789abcdef" in lifecycle
        assert "build-secret" not in lifecycle

        unsafe_answer = AssistantAnswer(
            summary="safe",
            basis="safe",
            risks_caveats="safe",
            tool_trace_summary="safe",
            research_metadata={
                "degradation": {
                    "warning": "AI synthesis unavailable; showing deterministic result.",
                    "stage": "SYNTHESIS_CALL",
                    "category": "GATEWAY_FAILURE",
                    "correlation_id": "prompt=secret",
                    "trace_id": "provider-payload",
                    "model_route": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd",
                    "build_sha": "api_key=secret",
                }
            },
        )
        unsafe_warning = degradation_warning(unsafe_answer)
        assert unsafe_warning is not None
        assert "secret" not in unsafe_warning
        assert "trace_id=" not in unsafe_warning
        assert "model_route=" not in unsafe_warning

        request_with_raw_context = AssistantRequest(
            current_user_prompt="safe prompt",
            workspace_context="private workspace payload",
            routing_session_id="private routing session",
            chat_context=ChatContext(
                last_plan="private plan payload",
                last_tool_outputs_summary="private tool output payload",
            ),
        )
        persisted_request = request_with_raw_context.to_dict()
        assert persisted_request["current_user_prompt"] is None
        assert persisted_request["workspace_context"] is None
        assert persisted_request["chat_context"] is None
        assert persisted_request["routing_session_id"] is None

        with monkeypatch.context() as finalization_patch:
            finalization_patch.setattr(
                "vnalpha.assistant.connected_execute.finish_prepared_turn",
                trace_failure,
            )
            prepared_turn_failure_result, _ = AssistantApp(
                conn, llm_client=ValidSynthesisGateway()
            ).ask("thi truong hom nay", date="2026-07-01")
        assert isinstance(prepared_turn_failure_result, AssistantAnswer)
        assert (
            prepared_turn_failure_result.research_metadata["degradation"]["stage"]
            == "SESSION_FINALIZE"
        )
        assert conn.execute(
            "SELECT status FROM assistant_session ORDER BY started_at DESC LIMIT 1"
        ).fetchone() == ("DEGRADED_SUCCESS",)

        class FailingClassificationGateway:
            last_raw_responses: tuple[dict, ...] = ()

            def chat(self, *_args, **_kwargs):
                raise RuntimeError("gateway unavailable")

        with monkeypatch.context() as classify_patch:
            classify_patch.setattr(
                "vnalpha.assistant.connected_prepare.finish_llm_trace",
                trace_failure,
            )
            with pytest.raises(AssistantLifecycleError) as lifecycle_error:
                AssistantApp(conn, llm_client=FailingClassificationGateway()).ask(
                    "thi truong hom nay"
                )
        assert lifecycle_error.value.stage == AssistantFailureStage.CLASSIFY
        assert lifecycle_error.value.category == "CLASSIFICATION_FAILURE"
        assert conn.execute(
            "SELECT status FROM assistant_session ORDER BY started_at DESC LIMIT 1"
        ).fetchone() == ("FAILED",)

        raw_model_payload = "NONJSON-MODEL-PAYLOAD-DO-NOT-PERSIST-4f31f"

        class InvalidJsonClassificationGateway:
            last_raw_responses: tuple[dict, ...] = ()

            def chat(self, *_args, **_kwargs):
                return raw_model_payload, {"total_tokens": 1}

        with pytest.raises(AssistantLifecycleError) as lifecycle_error:
            AssistantApp(conn, llm_client=InvalidJsonClassificationGateway()).ask(
                "thi truong hom nay"
            )
        assert lifecycle_error.value.trace_id is not None
        trace_error = conn.execute(
            "SELECT error_json FROM llm_trace WHERE llm_trace_id = ?",
            [lifecycle_error.value.trace_id],
        ).fetchone()
        assert trace_error is not None
        assert raw_model_payload not in trace_error[0]
        session_error = conn.execute(
            "SELECT error_json FROM assistant_session WHERE assistant_session_id = ("
            "SELECT assistant_session_id FROM llm_trace WHERE llm_trace_id = ?)",
            [lifecycle_error.value.trace_id],
        ).fetchone()
        assert session_error is not None
        assert raw_model_payload not in session_error[0]

        with monkeypatch.context() as trace_patch:
            trace_patch.setattr(
                "vnalpha.assistant.connected_prepare.finish_llm_trace",
                trace_failure,
            )
            with pytest.raises(AssistantLifecycleError) as lifecycle_error:
                AssistantApp(conn, llm_client=ValidSynthesisGateway()).ask(
                    "thi truong hom nay"
                )
        assert lifecycle_error.value.stage == AssistantFailureStage.AUDIT_PERSIST
        assert lifecycle_error.value.category == "CLASSIFY_TRACE_PERSIST_FAILURE"
        assert conn.execute(
            "SELECT status FROM assistant_session ORDER BY started_at DESC LIMIT 1"
        ).fetchone() == ("FAILED",)

        warehouse_path = tmp_path / "managed-assistant.duckdb"
        managed_conn = duckdb.connect(str(warehouse_path))
        run_migrations(conn=managed_conn)
        managed_conn.close()
        with monkeypatch.context() as trace_patch:
            trace_patch.setattr(
                "vnalpha.assistant.managed_prepare.finish_llm_trace",
                trace_failure,
            )
            with pytest.raises(AssistantLifecycleError) as lifecycle_error:
                AssistantApp.managed(
                    llm_client=ValidSynthesisGateway(), warehouse_path=warehouse_path
                ).ask("thi truong hom nay")
        assert lifecycle_error.value.stage == AssistantFailureStage.AUDIT_PERSIST
        assert lifecycle_error.value.category == "CLASSIFY_TRACE_PERSIST_FAILURE"
        managed_conn = duckdb.connect(str(warehouse_path), read_only=True)
        assert managed_conn.execute(
            "SELECT status FROM assistant_session ORDER BY started_at DESC LIMIT 1"
        ).fetchone() == ("FAILED",)
        managed_conn.close()

        def session_failure(*_args, **_kwargs):
            raise RuntimeError("session unavailable")

        monkeypatch.setattr(
            "vnalpha.assistant.connected_execute.finish_assistant_session",
            session_failure,
        )
        finalize_result, _ = AssistantApp(conn, llm_client=ValidSynthesisGateway()).ask(
            "thi truong hom nay", date="2026-07-01"
        )
        assert isinstance(finalize_result, AssistantAnswer)
        assert finalize_result.research_metadata["degradation"]["stage"] == (
            "SESSION_FINALIZE"
        )


# ===========================================================================
# AssistantApp tests
# ===========================================================================
