"""Error and validation handling for the vnalpha chat system (Section 11)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

from rich.markup import escape

from vnalpha.core.text_safety import sanitize_text

MAX_PUBLIC_ERROR_CHARS: Final = 4_096
_PUBLIC_ERROR_SUFFIX_CHARS: Final = MAX_PUBLIC_ERROR_CHARS * 3 // 4
_PUBLIC_ERROR_SCAN_CHARS: Final = MAX_PUBLIC_ERROR_CHARS * 2


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


def sanitize_public_error(message: str) -> str:
    """Return safe bounded text while retaining its actionable suffix."""
    raw = message
    if len(raw) > _PUBLIC_ERROR_SCAN_CHARS:
        prefix_chars = _PUBLIC_ERROR_SCAN_CHARS // 4
        suffix_chars = _PUBLIC_ERROR_SCAN_CHARS - prefix_chars - 1
        raw = raw[:prefix_chars] + "…" + raw[-suffix_chars:]
    sanitized = escape(" ".join(sanitize_text(raw).split()))
    if len(sanitized) <= MAX_PUBLIC_ERROR_CHARS:
        return sanitized
    prefix_chars = MAX_PUBLIC_ERROR_CHARS - _PUBLIC_ERROR_SUFFIX_CHARS - 1
    return (
        sanitized[:prefix_chars].rstrip()
        + "…"
        + sanitized[-_PUBLIC_ERROR_SUFFIX_CHARS:].lstrip()
    )


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
