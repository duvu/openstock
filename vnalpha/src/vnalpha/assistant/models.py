from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from vnalpha.assistant.research_intelligence_intents import (
    RESEARCH_INTELLIGENCE_INTENTS,
)

if TYPE_CHECKING:
    from vnalpha.chat.context import ChatContext


class AssistantSessionStatus(str, Enum):
    RUNNING = "RUNNING"
    PREPARED = "PREPARED"
    SUCCESS = "SUCCESS"
    REFUSED = "REFUSED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    FAILED = "FAILED"


class LLMTraceStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class LLMStage(str, Enum):
    CLASSIFY = "classify"
    PLAN = "plan"
    SYNTHESIZE = "synthesize"


_BASE_SUPPORTED_INTENTS = frozenset(
    {
        "scan_candidates",
        "filter_candidates",
        "compare_symbols",
        "explain_symbol",
        "review_quality",
        "review_symbol_sector_alignment",
        "show_lineage",
        "summarize_watchlist",
        "create_research_note",
        "show_history",
        "fetch_data",
        "sandbox_research_calculation",
        "unsupported_or_unsafe",
    }
)

SUPPORTED_INTENTS: frozenset[str] = (
    _BASE_SUPPORTED_INTENTS | RESEARCH_INTELLIGENCE_INTENTS
)


@dataclass
class IntentResult:
    intent: str
    confidence: float
    entities: dict[str, Any]
    needs_clarification: bool = False
    clarification_question: str | None = None
    safety_flags: list[str] = field(default_factory=list)


@dataclass
class ToolPlanStep:
    step_id: str
    tool_name: str
    arguments: dict[str, Any]
    purpose: str
    required_permission: str

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class AssistantPlan:
    intent: str
    steps: list[ToolPlanStep]
    assumptions: list[str] = field(default_factory=list)
    required_artifacts: list[str] = field(default_factory=list)
    refusal_reason: str | None = None

    def is_refusal(self) -> bool:
        return self.refusal_reason is not None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass(frozen=True, slots=True)
class AssistantRequest:
    """Typed boundary separating the current request from historical context."""

    current_user_prompt: str
    workspace_context: str | None = None
    chat_context: "ChatContext | None" = None
    date: str | None = None
    routing_session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        context = (
            dataclasses.asdict(self.chat_context)
            if self.chat_context is not None
            else None
        )
        return {
            "current_user_prompt": self.current_user_prompt,
            "workspace_context": self.workspace_context,
            "chat_context": context,
            "date": self.date,
            "routing_session_id": self.routing_session_id,
        }


@dataclass(frozen=True, slots=True)
class PromptPersistenceRecord:
    """Bounded assistant prompt projection persisted in the warehouse."""

    prompt_text: str | None
    prompt_summary: str
    prompt_hash: str
    prompt_chars: int
    workspace_context_ref: str | None
    chat_context_ref: str | None
    raw_stored: bool

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True, slots=True)
class PreparedAssistantTurn:
    """One immutable prepared plan that may be previewed or executed exactly."""

    prepared_turn_id: str
    assistant_session_id: str
    request: AssistantRequest
    intent_result: IntentResult
    plan: AssistantPlan
    plan_hash: str
    policy_status: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "prepared_turn_id": self.prepared_turn_id,
            "assistant_session_id": self.assistant_session_id,
            "request": self.request.to_dict(),
            "intent_result": dataclasses.asdict(self.intent_result),
            "plan": self.plan.to_dict(),
            "plan_hash": self.plan_hash,
            "policy_status": self.policy_status,
            "created_at": self.created_at,
        }


def canonical_plan_json(plan: AssistantPlan) -> str:
    """Serialize a plan deterministically for approval identity checks."""

    return json.dumps(
        plan.to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def plan_hash(plan: AssistantPlan) -> str:
    """Return the SHA-256 identity of a canonical plan."""

    return hashlib.sha256(canonical_plan_json(plan).encode("utf-8")).hexdigest()


def text_hash(text: str) -> str:
    """Return a stable SHA-256 identity for a bounded text projection."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class AssistantAnswer:
    summary: str
    basis: str
    risks_caveats: str
    tool_trace_summary: str
    missing_data: list[str] = field(default_factory=list)
    raw_tool_outputs: dict[str, Any] = field(default_factory=dict)
    grounded_source_refs: list[str] = field(default_factory=list)
    research_metadata: dict[str, Any] = field(default_factory=dict)
    claim_source_refs: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class RefusalMessage:
    reason: str
    # TRADING_EXECUTION | UNAVAILABLE_TOOL | SAFETY_BYPASS | DATA_FABRICATION
    policy_category: str
    suggestion: str | None = None


@dataclass
class AssistantSessionRecord:
    assistant_session_id: str
    started_at: str
    status: str
    surface: str
    user_prompt: str
    intent: str | None = None
    plan_json: str | None = None
    answer_json: str | None = None
    refusal_reason: str | None = None
    error_json: str | None = None
    finished_at: str | None = None


@dataclass
class LLMTraceRecord:
    llm_trace_id: str
    assistant_session_id: str
    stage: str
    started_at: str
    status: str
    model: str | None = None
    input_summary_json: str | None = None
    output_summary_json: str | None = None
    usage_json: str | None = None
    error_json: str | None = None
    finished_at: str | None = None
