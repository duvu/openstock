"""Error and validation handling for the vnalpha chat system (Section 11)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ChatErrorKind(str, Enum):
    """Categories of chat errors."""

    VALIDATION = "validation"
    RUNTIME = "runtime"
    REFUSAL = "refusal"
    TOOL_FAILED = "tool_failed"


@dataclass
class ChatError:
    """A structured chat error with kind, message, and optional detail."""

    kind: ChatErrorKind
    message: str
    detail: str | None = None


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_validation_error(msg: str) -> str:
    """Return a formatted validation error string."""
    return f"[WARNING] {msg}"


def format_runtime_error(msg: str, detail: str | None = None) -> str:
    """Return a formatted runtime error string, optionally including detail."""
    if detail:
        return f"[ERROR] {msg}: {detail}"
    return f"[ERROR] {msg}"


def format_refusal(msg: str) -> str:
    """Return a formatted refusal string."""
    return f"[REFUSED] {msg}"


def format_tool_failure(tool_name: str, error: str) -> str:
    """Return a formatted tool failure string."""
    return f"[TOOL FAILED] {tool_name}: {error}"


# ---------------------------------------------------------------------------
# message_type mapping
# ---------------------------------------------------------------------------

_KIND_TO_MESSAGE_TYPE: dict[ChatErrorKind, str] = {
    ChatErrorKind.VALIDATION: "validation_error",
    ChatErrorKind.RUNTIME: "error",
    ChatErrorKind.REFUSAL: "refusal",
    ChatErrorKind.TOOL_FAILED: "tool_trace_event",
}


def error_to_message_type(kind: ChatErrorKind) -> str:
    """Map a ChatErrorKind to the corresponding chat_message message_type string."""
    return _KIND_TO_MESSAGE_TYPE[kind]
