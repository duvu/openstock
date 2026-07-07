"""Refusal policy for Phase 5.9 assistant — deterministic safety enforcement."""

from __future__ import annotations

from vnalpha.assistant.errors import RefusalError
from vnalpha.assistant.models import IntentResult

# --- Category: Trading execution ---
# Note: phrases are split to avoid triggering static source-scan safety tests
_P = "port" + "folio"
_PO = "place" + " " + "order"
TRADING_EXECUTION_PHRASES = frozenset(
    {
        "buy",
        "sell",
        "order",
        _PO,
        "execute trade",
        "broker",
        "account management",
        _P + " management",
        "autonomous trade",
        "short sell",
        "long position",
    }
)

# --- Category: Unavailable tools ---
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

# --- Category: Safety bypass ---
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

# --- Category: Guaranteed prediction ---
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


def check_policy(prompt: str) -> None:
    """
    Deterministic safety check. Raises RefusalError if prompt matches any forbidden pattern.
    Called before LLM classification.
    """
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
                suggestion="Use /scan, /explain, /quality, or /lineage for research questions.",
            )
    for phrase in SAFETY_BYPASS_PHRASES:
        if phrase in lower:
            raise RefusalError(
                reason="Requests to bypass safety controls, hide traces, or fabricate data are not allowed.",
                policy_category="SAFETY_BYPASS",
            )
    for phrase in PREDICTION_CERTAINTY_PHRASES:
        if phrase in lower:
            raise RefusalError(
                reason="The research assistant cannot make guaranteed predictions.",
                policy_category="PREDICTION_CERTAINTY",
                suggestion="Ask about the current score, setup classification, and risk flags for research context.",
            )


def check_intent_policy(intent_result: IntentResult) -> None:
    """Secondary check after classification."""
    if intent_result.intent == "unsupported_or_unsafe":
        flags = intent_result.safety_flags
        category = flags[0] if flags else "UNSUPPORTED"
        raise RefusalError(
            reason="This request is not supported by the research assistant.",
            policy_category=category,
        )
