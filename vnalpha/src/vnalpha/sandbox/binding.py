from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

import duckdb

from vnalpha.assistant.models import (
    AssistantPlan,
    AssistantRequest,
    IntentResult,
    PreparedAssistantTurn,
    ToolPlanStep,
    plan_hash,
)
from vnalpha.warehouse.assistant_repo import (
    create_assistant_session,
    mark_assistant_session_prepared,
    persist_prepared_turn,
)

_SANDBOX_INTENT = "sandbox_research_calculation"


class SandboxPlanMaterializer(Protocol):
    def materialize_assistant_plan(self, plan: AssistantPlan) -> AssistantPlan: ...


@dataclass(frozen=True, slots=True)
class SandboxTurnRequest:
    purpose: str
    raw_request: str
    surface: str


def prepare_sandbox_turn(
    conn: duckdb.DuckDBPyConnection,
    materializer: SandboxPlanMaterializer,
    request: SandboxTurnRequest,
) -> PreparedAssistantTurn:
    plan = materializer.materialize_assistant_plan(
        AssistantPlan(
            intent=_SANDBOX_INTENT,
            steps=[
                ToolPlanStep(
                    step_id=f"step-sandbox-{uuid4().hex}",
                    tool_name="sandbox.run_research_code",
                    arguments={"purpose": request.purpose},
                    purpose="Prepare an approval-gated numeric research calculation",
                    required_permission="SANDBOX_APPROVAL",
                )
            ],
        )
    )
    session_id = create_assistant_session(
        conn,
        surface=request.surface,
        user_prompt=request.raw_request,
        intent=_SANDBOX_INTENT,
    )
    turn = PreparedAssistantTurn(
        prepared_turn_id=f"turn-{uuid4().hex}",
        assistant_session_id=session_id,
        request=AssistantRequest(current_user_prompt=request.raw_request),
        intent_result=IntentResult(
            intent=_SANDBOX_INTENT,
            confidence=1.0,
            entities={"purpose": request.purpose},
        ),
        plan=plan,
        plan_hash=plan_hash(plan),
        policy_status="PASS",
        created_at=datetime.now(UTC).isoformat(),
    )
    persist_prepared_turn(conn, turn)
    mark_assistant_session_prepared(
        conn, session_id, intent=_SANDBOX_INTENT, plan=plan.to_dict()
    )
    return turn
