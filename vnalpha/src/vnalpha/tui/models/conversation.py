"""Conversation message models for the TUI transcript.

These message types are intentionally small and immutable so that UI rendering can
be tested independently from command/chat execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageKind(str, Enum):
    """Classify a row in the TUI transcript stream."""

    USER = "user"
    ASSISTANT = "assistant"
    COMMAND_RESULT = "command_result"
    ACTIVITY = "activity"
    WARNING = "warning"
    ERROR = "error"
    APPROVAL_REQUEST = "approval_request"


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    """Base immutable message carried by the transcript view."""

    kind: MessageKind
    text: str


@dataclass(frozen=True, slots=True)
class UserMessage(ConversationMessage):
    """A user-submitted message (command or natural-language text)."""

    prompt_type: str = "natural"

    def __init__(self, text: str, prompt_type: str = "natural") -> None:
        ConversationMessage.__init__(self, MessageKind.USER, text)
        object.__setattr__(self, "prompt_type", prompt_type)


@dataclass(frozen=True, slots=True)
class AssistantAnswerMessage(ConversationMessage):
    """Structured assistant answer with source-aware fields."""

    basis: str = ""
    risks_caveats: str = ""
    missing_data: list[str] = field(default_factory=list)
    grounded_source_refs: list[str] = field(default_factory=list)
    claim_source_refs: dict[str, list[str]] = field(default_factory=dict)
    research_metadata: dict[str, Any] | None = None
    tool_trace_summary: str = ""
    summary: str = ""

    def __init__(
        self,
        text: str,
        summary: str = "",
        *,
        basis: str = "",
        risks_caveats: str = "",
        missing_data: list[str] | None = None,
        grounded_source_refs: list[str] | None = None,
        claim_source_refs: dict[str, list[str]] | None = None,
        research_metadata: dict[str, Any] | None = None,
        tool_trace_summary: str = "",
    ) -> None:
        ConversationMessage.__init__(self, MessageKind.ASSISTANT, text)
        object.__setattr__(self, "summary", summary)
        object.__setattr__(self, "basis", basis)
        object.__setattr__(self, "risks_caveats", risks_caveats)
        object.__setattr__(self, "missing_data", list(missing_data or []))
        object.__setattr__(
            self, "grounded_source_refs", list(grounded_source_refs or [])
        )
        object.__setattr__(self, "claim_source_refs", dict(claim_source_refs or {}))
        object.__setattr__(self, "research_metadata", research_metadata)
        object.__setattr__(self, "tool_trace_summary", tool_trace_summary)

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", self.summary or self.text)
        object.__setattr__(
            self, "missing_data", list(self.missing_data) if self.missing_data else []
        )
        object.__setattr__(
            self,
            "grounded_source_refs",
            list(self.grounded_source_refs) if self.grounded_source_refs else [],
        )
        object.__setattr__(
            self,
            "claim_source_refs",
            dict(self.claim_source_refs) if self.claim_source_refs else {},
        )

    def source_counts(self) -> tuple[int, int]:
        """Return ``(num_sources, num_missing_data_items)`` for summary chips."""

        return len(self.grounded_source_refs), len(self.missing_data)


@dataclass(frozen=True, slots=True)
class CommandResultMessage(ConversationMessage):
    """Result of a slash command / command-like operation."""

    command: str
    command_status: str = "success"

    def __init__(
        self, command: str, result: str, command_status: str = "success"
    ) -> None:
        ConversationMessage.__init__(self, MessageKind.COMMAND_RESULT, result)
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "command_status", command_status)


@dataclass(frozen=True, slots=True)
class ActivityMessage(ConversationMessage):
    """Streaming activity / stage updates."""

    detail: str | None = None
    elapsed_ms: int | None = None

    def __init__(
        self, text: str, detail: str | None = None, elapsed_ms: int | None = None
    ) -> None:
        ConversationMessage.__init__(self, MessageKind.ACTIVITY, text)
        object.__setattr__(self, "detail", detail)
        object.__setattr__(self, "elapsed_ms", elapsed_ms)


@dataclass(frozen=True, slots=True)
class WarningMessage(ConversationMessage):
    """A warning line in transcript."""

    source: str | None = None

    def __init__(self, text: str, source: str | None = None) -> None:
        ConversationMessage.__init__(self, MessageKind.WARNING, text)
        object.__setattr__(self, "source", source)


@dataclass(frozen=True, slots=True)
class ErrorMessage(ConversationMessage):
    """An error line in transcript."""

    source: str | None = None

    def __init__(self, text: str, source: str | None = None) -> None:
        ConversationMessage.__init__(self, MessageKind.ERROR, text)
        object.__setattr__(self, "source", source)


@dataclass(frozen=True, slots=True)
class ApprovalRequestMessage(ConversationMessage):
    """Approval-state card for pending tool execution."""

    tools: list[str]
    permissions: str = ""

    def __init__(self, tools: list[str], permissions: str = "") -> None:
        ConversationMessage.__init__(
            MessageKind.APPROVAL_REQUEST,
            "Plan prepared and waiting for approval.",
        )
        object.__setattr__(self, "tools", list(tools))
        object.__setattr__(self, "permissions", permissions)
