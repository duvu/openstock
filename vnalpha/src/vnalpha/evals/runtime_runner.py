from __future__ import annotations

import json
from pathlib import Path
from typing import assert_never

import duckdb

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.errors import AssistantInputValidationError
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    AssistantRequest,
    PreparedAssistantTurn,
    RefusalMessage,
)
from vnalpha.evals.network_guard import prohibit_network
from vnalpha.evals.runtime_adapter import seeded_assistant_executor
from vnalpha.evals.runtime_models import (
    AuditExpectation,
    ExpectedPlanStep,
    ObservedResearchMetadata,
    RuntimeOutcome,
    RuntimeReplayCase,
)
from vnalpha.evals.runtime_report import (
    RuntimeCheckResult,
    RuntimeReplayCaseResult,
    RuntimeReplayReport,
)
from vnalpha.tools.executor import TraceEvent
from vnalpha.warehouse.migrations import run_migrations


def run_runtime_replay_case(case: RuntimeReplayCase) -> RuntimeReplayCaseResult:
    responses = []
    if case.classifier_response is not None:
        responses.append((case.classifier_response.model_dump_json(), {}))
    if case.synthesis_response is not None:
        responses.append((case.synthesis_response.model_dump_json(), {}))
    client = FakeLLMClient(responses)
    traces: list[TraceEvent] = []

    with prohibit_network(), duckdb.connect(":memory:") as conn:
        run_migrations(conn)
        app = AssistantApp(conn, surface="eval-runtime", llm_client=client)
        request = AssistantRequest(
            current_user_prompt=case.request.current_user_prompt,
            workspace_context=case.request.workspace_context,
            date=case.request.date,
        )
        with seeded_assistant_executor(case):
            try:
                prepared = app.prepare(request)
            except AssistantInputValidationError as exc:
                observation = _validation_error_observation(case, client, str(exc))
            else:
                match prepared:
                    case PreparedAssistantTurn():
                        answer, plan = app.execute_prepared(
                            prepared, on_trace_event=traces.append
                        )
                        observation = _answer_observation(
                            conn,
                            case,
                            client,
                            answer,
                            plan,
                            traces,
                            prepared.assistant_session_id,
                        )
                    case (RefusalMessage(), AssistantPlan() as plan):
                        observation = _refusal_observation(case, client, plan)
                    case unreachable:
                        assert_never(unreachable)
    return RuntimeReplayCaseResult(case_id=case.case_id, checks=observation)


def run_runtime_replay_corpus(root: Path | None = None) -> RuntimeReplayReport:
    from vnalpha.evals.runtime_corpus import run_runtime_replay_corpus as run_corpus

    return run_corpus(root)


def _answer_observation(
    conn: duckdb.DuckDBPyConnection,
    case: RuntimeReplayCase,
    client: FakeLLMClient,
    answer: AssistantAnswer | RefusalMessage,
    plan: AssistantPlan,
    traces: list[TraceEvent],
    assistant_session_id: str,
) -> tuple[RuntimeCheckResult, ...]:
    match answer:
        case AssistantAnswer():
            metadata = ObservedResearchMetadata.model_validate_json(
                json.dumps(answer.research_metadata, default=str, sort_keys=True)
            )
        case RefusalMessage():
            return _base_checks(case, RuntimeOutcome.REFUSAL, plan)
        case unreachable:
            assert_never(unreachable)

    successful_tools = tuple(
        trace.tool_name for trace in traces if trace.status == "SUCCESS"
    )
    groundedness_status = (
        metadata.groundedness.status.value
        if metadata.groundedness is not None
        else None
    )
    policy_status = (
        metadata.policy.status.value if metadata.policy is not None else None
    )
    audit_count = conn.execute(
        "SELECT COUNT(*) FROM research_answer_audit WHERE assistant_session_id = ?",
        [assistant_session_id],
    ).fetchone()[0]
    audit_status = (
        AuditExpectation.PERSISTED if audit_count == 1 else AuditExpectation.ABSENT
    )
    missing_required = tuple(
        value
        for value in case.expected.required_missing_data
        if value not in answer.missing_data
    )
    forbidden_refs = tuple(
        value
        for value in case.expected.forbidden_source_refs
        if value in answer.grounded_source_refs
    )
    checks = [
        *_base_checks(case, RuntimeOutcome.ANSWER, plan),
        _check(
            "successful_trace_tools",
            case.expected.successful_trace_tools,
            successful_tools,
        ),
        _check(
            "groundedness_status",
            _enum_value(case.expected.groundedness_status),
            groundedness_status,
        ),
        _check(
            "policy_status",
            _enum_value(case.expected.policy_status),
            policy_status,
        ),
        _check("fallback_used", case.expected.fallback_used, metadata.fallback_used),
        _check("audit_status", case.expected.audit_status.value, audit_status.value),
        _check("required_missing_data", (), missing_required),
        _check("forbidden_source_refs", (), forbidden_refs),
        _check(
            "claim_source_refs",
            case.expected.claim_source_refs,
            metadata.claim_source_refs,
        ),
        _check(
            "classifier_context_isolation",
            True,
            _classifier_context_isolated(case, client),
        ),
    ]
    return tuple(checks)


def _refusal_observation(
    case: RuntimeReplayCase,
    client: FakeLLMClient,
    plan: AssistantPlan,
) -> tuple[RuntimeCheckResult, ...]:
    return (
        *_base_checks(case, RuntimeOutcome.REFUSAL, plan),
        _check("successful_trace_tools", case.expected.successful_trace_tools, ()),
        _check(
            "groundedness_status", _enum_value(case.expected.groundedness_status), None
        ),
        _check("policy_status", _enum_value(case.expected.policy_status), None),
        _check("fallback_used", case.expected.fallback_used, None),
        _check("audit_status", case.expected.audit_status.value, "absent"),
        _check("required_missing_data", (), ()),
        _check("forbidden_source_refs", (), ()),
        _check("claim_source_refs", case.expected.claim_source_refs, {}),
        _check(
            "classifier_context_isolation",
            True,
            _classifier_context_isolated(case, client),
        ),
    )


def _validation_error_observation(
    case: RuntimeReplayCase,
    client: FakeLLMClient,
    message: str,
) -> tuple[RuntimeCheckResult, ...]:
    plan = AssistantPlan(intent=case.expected.intent, steps=[])
    expected_fragment = case.expected.validation_error_contains or ""
    actual_fragment = (
        expected_fragment if expected_fragment.lower() in message.lower() else message
    )
    return (
        *_base_checks(case, RuntimeOutcome.VALIDATION_ERROR, plan),
        _check("successful_trace_tools", case.expected.successful_trace_tools, ()),
        _check(
            "groundedness_status", _enum_value(case.expected.groundedness_status), None
        ),
        _check("policy_status", _enum_value(case.expected.policy_status), None),
        _check("fallback_used", case.expected.fallback_used, None),
        _check("audit_status", case.expected.audit_status.value, "absent"),
        _check("required_missing_data", (), ()),
        _check("forbidden_source_refs", (), ()),
        _check("claim_source_refs", case.expected.claim_source_refs, {}),
        _check("validation_error_contains", expected_fragment, actual_fragment),
        _check(
            "classifier_context_isolation",
            True,
            _classifier_context_isolated(case, client),
        ),
    )


def _base_checks(
    case: RuntimeReplayCase,
    outcome: RuntimeOutcome,
    plan: AssistantPlan,
) -> tuple[RuntimeCheckResult, ...]:
    actual_plan = tuple(
        ExpectedPlanStep(tool_name=step.tool_name, arguments=step.arguments)
        for step in plan.steps
    )
    return (
        _check("outcome", case.expected.outcome.value, outcome.value),
        _check("intent", case.expected.intent, plan.intent),
        _check("plan", case.expected.plan, actual_plan),
    )


def _classifier_context_isolated(
    case: RuntimeReplayCase, client: FakeLLMClient
) -> bool:
    historical_context = case.request.workspace_context
    if historical_context is None:
        return True
    if not client.calls:
        return case.expected.outcome in {
            RuntimeOutcome.REFUSAL,
            RuntimeOutcome.VALIDATION_ERROR,
        }
    return historical_context not in json.dumps(client.calls[0], sort_keys=True)


def _enum_value(value) -> str | None:
    return value.value if value is not None else None


def _check(name: str, expected, actual) -> RuntimeCheckResult:
    return RuntimeCheckResult(
        name=name,
        expected=_stable(expected),
        actual=_stable(actual),
    )


def _stable(value) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, tuple):
        value = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in value
        ]
    return json.dumps(value, default=str, ensure_ascii=False, sort_keys=True)
