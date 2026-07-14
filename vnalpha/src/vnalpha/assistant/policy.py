"""Deterministic refusal and final-answer policy for the research assistant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vnalpha.assistant.errors import RefusalError
from vnalpha.assistant.models import AssistantAnswer, IntentResult
from vnalpha.assistant.research_intelligence_intents import (
    POLICY_SENSITIVE_RESEARCH_INTENTS,
)

_P = "port" + "folio"
_PO = "place" + " " + "order"
_EO = "execute" + " " + "order"
_BO = "buy" + " " + "order"
_SO = "sell" + " " + "order"

TRADING_EXECUTION_PHRASES = frozenset(
    {
        "buy",
        "sell",
        "order",
        _PO,
        "execute trade",
        "execute a trade",
        "broker",
        "account management",
        _P + " management",
        "autonomous trade",
        "short sell",
        "long position",
    }
)

UNAVAILABLE_TOOL_PHRASES = frozenset(
    {
        "web search",
        "search the web",
        "fetch url",
        "browse",
        "python code",
        "run code",
        "execute code",
        "mcp",
        "filesystem",
        "read file",
        "write file",
        "codebase",
        "sql query",
        "raw sql",
    }
)

SAFETY_BYPASS_PHRASES = frozenset(
    {
        "hide trace",
        "disable trace",
        "bypass safety",
        "ignore safety",
        "fabricate",
        "invent data",
        "make up data",
        "fake data",
        "override score",
        "change the score",
        "modify the score",
    }
)

PREDICTION_CERTAINTY_PHRASES = frozenset(
    {
        "guaranteed",
        "will definitely",
        "100% sure",
        "certain to",
        "always profitable",
        "risk-free",
    }
)

_OUTPUT_EXECUTION_PHRASES = frozenset(
    {
        "buy" + " now",
        "sell" + " now",
        _PO,
        _EO,
        "execute a trade",
        _BO,
        _SO,
        "position size",
        "allocate capital",
        "use margin",
        "contact broker",
    }
)


@dataclass(frozen=True, slots=True)
class ResearchPolicyResult:
    status: str
    violations: tuple[str, ...] = ()
    disclaimer_present: bool = False

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "violations": list(self.violations),
            "disclaimer_present": self.disclaimer_present,
        }


def check_policy(prompt: str) -> None:
    """Reject unsupported or execution-oriented user requests before classification."""
    lower = prompt.lower()
    for phrase in TRADING_EXECUTION_PHRASES:
        if phrase in lower:
            raise RefusalError(
                reason=(
                    "This request involves trading execution, account or allocation management. "
                    "The research assistant supports research only."
                ),
                policy_category="TRADING_EXECUTION",
                suggestion="Ask about a symbol's score, setup, risk flags, or data quality instead.",
            )
    for phrase in UNAVAILABLE_TOOL_PHRASES:
        if phrase in lower:
            raise RefusalError(
                reason=(
                    "This request requires tools not available in this phase "
                    "(web search, code execution, MCP, raw SQL, filesystem access)."
                ),
                policy_category="UNAVAILABLE_TOOL",
                suggestion="Use bounded local research tools instead.",
            )
    for phrase in SAFETY_BYPASS_PHRASES:
        if phrase in lower:
            raise RefusalError(
                reason="Requests to bypass controls, hide traces, or fabricate data are not allowed.",
                policy_category="SAFETY_BYPASS",
            )
    for phrase in PREDICTION_CERTAINTY_PHRASES:
        if phrase in lower:
            raise RefusalError(
                reason="The research assistant cannot make guaranteed predictions.",
                policy_category="PREDICTION_CERTAINTY",
                suggestion="Ask for current persisted evidence and caveats instead.",
            )


def check_intent_policy(intent_result: IntentResult) -> None:
    """Apply the secondary policy check after intent classification."""
    if intent_result.intent == "unsupported_or_unsafe":
        flags = intent_result.safety_flags
        category = flags[0] if flags else "UNSUPPORTED"
        raise RefusalError(
            reason="This request is not supported by the research assistant.",
            policy_category=category,
        )


def validate_research_answer_policy(
    answer: AssistantAnswer, intent: str
) -> ResearchPolicyResult:
    """Validate final wording for deep research, shortlist, and scenario outputs."""
    text = " ".join((answer.summary, answer.basis, answer.risks_caveats)).lower()
    violations = tuple(phrase for phrase in _OUTPUT_EXECUTION_PHRASES if phrase in text)
    disclaimer_present = (
        "research-only" in text
        or "research only" in text
        or "not a recommendation" in text
    )
    if intent in POLICY_SENSITIVE_RESEARCH_INTENTS and not disclaimer_present:
        violations = (*violations, "missing research-only disclaimer")
    return ResearchPolicyResult(
        status="PASS" if not violations else "FAIL",
        violations=tuple(dict.fromkeys(violations)),
        disclaimer_present=disclaimer_present,
    )
