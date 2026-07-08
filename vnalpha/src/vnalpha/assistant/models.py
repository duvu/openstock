from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Status enums
# ---------------------------------------------------------------------------


class AssistantSessionStatus(str, Enum):
    RUNNING = "RUNNING"
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


# ---------------------------------------------------------------------------
# Supported intent names
# ---------------------------------------------------------------------------

SUPPORTED_INTENTS: frozenset[str] = frozenset(
    {
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
)


# ---------------------------------------------------------------------------
# Core domain dataclasses
# ---------------------------------------------------------------------------


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


@dataclass
class AssistantAnswer:
    summary: str
    basis: str
    risks_caveats: str
    tool_trace_summary: str
    missing_data: list[str] = field(default_factory=list)
    raw_tool_outputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class RefusalMessage:
    reason: str
    # TRADING_EXECUTION | UNAVAILABLE_TOOL | SAFETY_BYPASS | DATA_FABRICATION
    policy_category: str
    suggestion: str | None = None


# ---------------------------------------------------------------------------
# DB record dataclasses (type-safe repo layer)
# ---------------------------------------------------------------------------


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
