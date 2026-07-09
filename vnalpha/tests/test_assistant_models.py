"""Tests for Phase 5.9 assistant core models, errors, and LLM gateway."""

from __future__ import annotations

from vnalpha.assistant.errors import (
    AssistantError,
    IntentClassificationError,
    LLMGatewayError,
    LLMResponseError,
    LLMTimeoutError,
    PlanBuildError,
    PlanValidationError,
    RefusalError,
    SynthesisError,
    ToolExecutionError,
)
from vnalpha.assistant.gateway import (
    ASSISTANT_ENDPOINT_DEFAULT,
    ASSISTANT_MAX_OUTPUT_TOKENS_DEFAULT,
    ASSISTANT_MAX_RETRIES_DEFAULT,
    ASSISTANT_MODEL_DEFAULT,
    ASSISTANT_TIMEOUT_DEFAULT,
    FakeLLMClient,
    LLMGatewayConfig,
    redact_summary,
)
from vnalpha.assistant.models import (
    SUPPORTED_INTENTS,
    AssistantAnswer,
    AssistantPlan,
    AssistantSessionRecord,
    AssistantSessionStatus,
    IntentResult,
    LLMStage,
    LLMTraceRecord,
    LLMTraceStatus,
    ToolPlanStep,
)

# ---------------------------------------------------------------------------
# 1. AssistantSessionStatus enum values
# ---------------------------------------------------------------------------


def test_assistant_session_status_values():
    assert AssistantSessionStatus.RUNNING == "RUNNING"
    assert AssistantSessionStatus.SUCCESS == "SUCCESS"
    assert AssistantSessionStatus.REFUSED == "REFUSED"
    assert AssistantSessionStatus.VALIDATION_ERROR == "VALIDATION_ERROR"
    assert AssistantSessionStatus.FAILED == "FAILED"


# ---------------------------------------------------------------------------
# 2. LLMTraceStatus enum values
# ---------------------------------------------------------------------------


def test_llm_trace_status_values():
    assert LLMTraceStatus.RUNNING == "RUNNING"
    assert LLMTraceStatus.SUCCESS == "SUCCESS"
    assert LLMTraceStatus.FAILED == "FAILED"


# ---------------------------------------------------------------------------
# 3. LLMStage enum values
# ---------------------------------------------------------------------------


def test_llm_stage_values():
    assert LLMStage.CLASSIFY == "classify"
    assert LLMStage.PLAN == "plan"
    assert LLMStage.SYNTHESIZE == "synthesize"


# ---------------------------------------------------------------------------
# 4. SUPPORTED_INTENTS contains all 11 intent names
# ---------------------------------------------------------------------------


def test_supported_intents_all_ten():
    expected = {
        "scan_candidates",
        "filter_candidates",
        "compare_symbols",
        "explain_symbol",
        "review_quality",
        "show_lineage",
        "summarize_watchlist",
        "create_research_note",
        "show_history",
        "fetch_data",
        "unsupported_or_unsafe",
    }
    assert SUPPORTED_INTENTS == expected
    assert len(SUPPORTED_INTENTS) == 11


# ---------------------------------------------------------------------------
# 5. IntentResult dataclass creates with defaults
# ---------------------------------------------------------------------------


def test_intent_result_defaults():
    ir = IntentResult(intent="scan_candidates", confidence=0.9, entities={})
    assert ir.needs_clarification is False
    assert ir.clarification_question is None
    assert ir.safety_flags == []


# ---------------------------------------------------------------------------
# 6. ToolPlanStep creates and to_dict() works
# ---------------------------------------------------------------------------


def test_tool_plan_step_to_dict():
    step = ToolPlanStep(
        step_id="s1",
        tool_name="scan_tool",
        arguments={"sector": "banking"},
        purpose="list banking stocks",
        required_permission="read",
    )
    d = step.to_dict()
    assert d["step_id"] == "s1"
    assert d["tool_name"] == "scan_tool"
    assert d["arguments"] == {"sector": "banking"}
    assert d["purpose"] == "list banking stocks"
    assert d["required_permission"] == "read"


# ---------------------------------------------------------------------------
# 7. AssistantPlan is_refusal() returns True when refusal_reason set
# ---------------------------------------------------------------------------


def test_assistant_plan_is_refusal_true():
    plan = AssistantPlan(
        intent="scan_candidates",
        steps=[],
        refusal_reason="This action is not allowed.",
    )
    assert plan.is_refusal() is True


def test_assistant_plan_is_refusal_false():
    plan = AssistantPlan(intent="scan_candidates", steps=[])
    assert plan.is_refusal() is False


# ---------------------------------------------------------------------------
# 8. AssistantPlan.to_dict() serializes nested steps
# ---------------------------------------------------------------------------


def test_assistant_plan_to_dict_nested_steps():
    step = ToolPlanStep(
        step_id="s1",
        tool_name="scan_tool",
        arguments={"limit": 10},
        purpose="scan",
        required_permission="read",
    )
    plan = AssistantPlan(
        intent="scan_candidates",
        steps=[step],
        assumptions=["market is open"],
    )
    d = plan.to_dict()
    assert d["intent"] == "scan_candidates"
    assert isinstance(d["steps"], list)
    assert d["steps"][0]["tool_name"] == "scan_tool"
    assert d["assumptions"] == ["market is open"]
    assert d["refusal_reason"] is None


# ---------------------------------------------------------------------------
# 9. AssistantAnswer.to_dict() roundtrips
# ---------------------------------------------------------------------------


def test_assistant_answer_to_dict_roundtrip():
    answer = AssistantAnswer(
        summary="Top 5 candidates found.",
        basis="P/E < 15, ROE > 20%",
        risks_caveats="Data may be delayed.",
        tool_trace_summary="scan_tool called once.",
        missing_data=["Q4 earnings"],
        raw_tool_outputs={"scan_tool": [{"symbol": "VCB"}]},
    )
    d = answer.to_dict()
    assert d["summary"] == "Top 5 candidates found."
    assert d["basis"] == "P/E < 15, ROE > 20%"
    assert d["risks_caveats"] == "Data may be delayed."
    assert d["tool_trace_summary"] == "scan_tool called once."
    assert d["missing_data"] == ["Q4 earnings"]
    assert d["raw_tool_outputs"]["scan_tool"][0]["symbol"] == "VCB"


# ---------------------------------------------------------------------------
# 10. RefusalError stores reason/policy_category
# ---------------------------------------------------------------------------


def test_refusal_error_stores_fields():
    err = RefusalError(
        reason="Trading execution not supported.",
        policy_category="TRADING_EXECUTION",
        suggestion="Use a broker app instead.",
    )
    assert err.reason == "Trading execution not supported."
    assert err.policy_category == "TRADING_EXECUTION"
    assert err.suggestion == "Use a broker app instead."
    assert str(err) == "Trading execution not supported."
    assert isinstance(err, AssistantError)


def test_refusal_error_no_suggestion():
    err = RefusalError(reason="Unsafe.", policy_category="SAFETY_BYPASS")
    assert err.suggestion is None


# ---------------------------------------------------------------------------
# 11. LLMGatewayConfig.from_env() uses defaults
# ---------------------------------------------------------------------------


def test_llm_gateway_config_defaults(monkeypatch):
    for key in [
        "VNALPHA_LLM_MODEL",
        "VNALPHA_LLM_ENDPOINT",
        "VNALPHA_LLM_TIMEOUT",
        "VNALPHA_LLM_MAX_OUTPUT_TOKENS",
        "VNALPHA_LLM_MAX_RETRIES",
        "VNALPHA_LLM_STORE_RAW",
    ]:
        monkeypatch.delenv(key, raising=False)

    cfg = LLMGatewayConfig.from_env()
    assert ASSISTANT_MODEL_DEFAULT == "oc-gpt-5.4-mini"
    assert cfg.model == "oc-gpt-5.4-mini"
    assert cfg.endpoint == ASSISTANT_ENDPOINT_DEFAULT
    assert cfg.timeout == ASSISTANT_TIMEOUT_DEFAULT
    assert ASSISTANT_MAX_OUTPUT_TOKENS_DEFAULT == 16000
    assert cfg.max_output_tokens == 16000
    assert cfg.max_output_tokens == ASSISTANT_MAX_OUTPUT_TOKENS_DEFAULT
    assert cfg.max_retries == ASSISTANT_MAX_RETRIES_DEFAULT
    assert cfg.store_raw is False


# ---------------------------------------------------------------------------
# 12. LLMGatewayConfig.from_env() respects env vars
# ---------------------------------------------------------------------------


def test_llm_gateway_config_from_env(monkeypatch):
    monkeypatch.setenv("VNALPHA_LLM_MODEL", "gpt-4o")
    monkeypatch.setenv(
        "VNALPHA_LLM_ENDPOINT", "https://custom.endpoint/v1/chat/completions"
    )
    monkeypatch.setenv("VNALPHA_LLM_TIMEOUT", "60")
    monkeypatch.setenv("VNALPHA_LLM_MAX_OUTPUT_TOKENS", "2048")
    monkeypatch.setenv("VNALPHA_LLM_MAX_RETRIES", "5")
    monkeypatch.setenv("VNALPHA_LLM_STORE_RAW", "true")

    cfg = LLMGatewayConfig.from_env()
    assert cfg.model == "gpt-4o"
    assert cfg.endpoint == "https://custom.endpoint/v1/chat/completions"
    assert cfg.timeout == 60
    assert cfg.max_output_tokens == 2048
    assert cfg.max_retries == 5
    assert cfg.store_raw is True


# ---------------------------------------------------------------------------
# 13. redact_summary(None) returns None
# ---------------------------------------------------------------------------


def test_redact_summary_none():
    assert redact_summary(None) is None


# ---------------------------------------------------------------------------
# 14. redact_summary(long_string) truncates with "[redacted]"
# ---------------------------------------------------------------------------


def test_redact_summary_truncates():
    long_text = "x" * 300
    result = redact_summary(long_text)
    assert result is not None
    assert result.endswith("...[redacted]")
    assert len(result) == 200 + len("...[redacted]")


def test_redact_summary_short_unchanged():
    short = "hello"
    assert redact_summary(short) == "hello"


# ---------------------------------------------------------------------------
# 15. FakeLLMClient returns configured responses
# ---------------------------------------------------------------------------


def test_fake_llm_client_configured_responses():
    fake = FakeLLMClient(
        responses=[
            ('{"intent": "filter_candidates"}', {"prompt_tokens": 10}),
            ('{"intent": "explain_symbol"}', {"prompt_tokens": 20}),
        ]
    )
    r1, u1 = fake.chat([{"role": "user", "content": "first"}])
    r2, u2 = fake.chat([{"role": "user", "content": "second"}])
    assert r1 == '{"intent": "filter_candidates"}'
    assert u1 == {"prompt_tokens": 10}
    assert r2 == '{"intent": "explain_symbol"}'
    assert u2 == {"prompt_tokens": 20}


def test_fake_llm_client_default_response():
    fake = FakeLLMClient()
    text, usage = fake.chat([{"role": "user", "content": "hi"}])
    assert '"intent": "scan_candidates"' in text
    assert usage == {}


# ---------------------------------------------------------------------------
# 16. FakeLLMClient.calls captures message list
# ---------------------------------------------------------------------------


def test_fake_llm_client_captures_calls():
    fake = FakeLLMClient()
    msgs1 = [{"role": "user", "content": "first question"}]
    msgs2 = [{"role": "user", "content": "second question"}]
    fake.chat(msgs1)
    fake.chat(msgs2)
    assert len(fake.calls) == 2
    assert fake.calls[0] == msgs1
    assert fake.calls[1] == msgs2


# ---------------------------------------------------------------------------
# 17. AssistantSessionRecord and LLMTraceRecord create correctly
# ---------------------------------------------------------------------------


def test_assistant_session_record_fields():
    rec = AssistantSessionRecord(
        assistant_session_id="sess-001",
        started_at="2026-07-06T10:00:00",
        status="RUNNING",
        surface="cli",
        user_prompt="List top banking stocks",
    )
    assert rec.assistant_session_id == "sess-001"
    assert rec.intent is None
    assert rec.plan_json is None
    assert rec.finished_at is None


def test_llm_trace_record_fields():
    rec = LLMTraceRecord(
        llm_trace_id="trace-001",
        assistant_session_id="sess-001",
        stage="classify",
        started_at="2026-07-06T10:00:01",
        status="SUCCESS",
        model="oc-gpt-5.4-mini",
    )
    assert rec.llm_trace_id == "trace-001"
    assert rec.input_summary_json is None
    assert rec.finished_at is None


# ---------------------------------------------------------------------------
# 18. Error hierarchy is correct
# ---------------------------------------------------------------------------


def test_error_hierarchy():
    assert issubclass(IntentClassificationError, AssistantError)
    assert issubclass(PlanBuildError, AssistantError)
    assert issubclass(PlanValidationError, AssistantError)
    assert issubclass(ToolExecutionError, AssistantError)
    assert issubclass(SynthesisError, AssistantError)
    assert issubclass(RefusalError, AssistantError)
    assert issubclass(LLMGatewayError, AssistantError)
    assert issubclass(LLMTimeoutError, LLMGatewayError)
    assert issubclass(LLMResponseError, LLMGatewayError)
