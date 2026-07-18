"""Error and validation handling for the vnalpha chat system (Section 11)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

from rich.markup import escape

from vnalpha.core.text_safety import sanitize_text
from vnalpha.tools.errors import PublicToolFailure

MAX_PUBLIC_ERROR_CHARS: Final = 4_096
_PUBLIC_ERROR_SCAN_CHARS: Final = MAX_PUBLIC_ERROR_CHARS * 2
_TOOL_FAILURE_PREFIX: Final = "[TOOL FAILED] "
_REMEDIATION_CHARS: Final = 1_536
_CORRELATION_CHARS: Final = 512


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


def sanitize_public_error(
    message: str, *, max_chars: int = MAX_PUBLIC_ERROR_CHARS
) -> str:
    if max_chars <= 0:
        return ""
    raw = message[:_PUBLIC_ERROR_SCAN_CHARS]
    sanitized = " ".join(sanitize_text(raw).split())
    escaped = escape(sanitized)
    if len(escaped) <= max_chars:
        return escaped
    return _escape_prefix(sanitized, max_chars - 1).rstrip() + "…"


def format_actionable_tool_failure(failure: PublicToolFailure) -> str:
    suffix_parts: list[str] = []
    if failure.remediation:
        remediation = sanitize_public_error(
            " -> ".join(failure.remediation), max_chars=_REMEDIATION_CHARS
        )
        if remediation:
            suffix_parts.append(f"Remediation: {remediation}")
    if failure.correlation_id:
        correlation_id = sanitize_public_error(
            failure.correlation_id, max_chars=_CORRELATION_CHARS
        )
        if correlation_id:
            suffix_parts.append(f"correlation_id={correlation_id}")

    suffix = ". ".join(suffix_parts)
    separator_chars = 2 if failure.reason and suffix else 0
    reason_chars = (
        MAX_PUBLIC_ERROR_CHARS
        - len(_TOOL_FAILURE_PREFIX)
        - len(suffix)
        - separator_chars
    )
    reason = sanitize_public_error(failure.reason.rstrip("."), max_chars=reason_chars)
    detail = ". ".join(part for part in (reason, suffix) if part)
    if not detail:
        detail = "Tool execution failed."
    return _TOOL_FAILURE_PREFIX + detail


def _escape_prefix(text: str, budget: int) -> str:
    low, high = 0, len(text)
    while low < high:
        midpoint = (low + high + 1) // 2
        if len(escape(text[:midpoint])) <= budget:
            low = midpoint
        else:
            high = midpoint - 1
    return escape(text[:low])


# ---------------------------------------------------------------------------
# message_type mapping
# ---------------------------------------------------------------------------

_KIND_TO_MESSAGE_TYPE: dict[ChatErrorKind, str] = {
    ChatErrorKind.VALIDATION: "validation_error",
    ChatErrorKind.RUNTIME: "error",
    ChatErrorKind.REFUSAL: "refusal",
    ChatErrorKind.TOOL_FAILED: "tool_failed",
}


def error_to_message_type(kind: ChatErrorKind) -> str:
    """Map a ChatErrorKind to the corresponding chat_message message_type string."""
    return _KIND_TO_MESSAGE_TYPE[kind]
