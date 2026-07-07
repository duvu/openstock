"""Streaming/staged response UX events for the vnalpha chat assistant."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AssistantStage(str, Enum):
    """Lifecycle stages emitted while the assistant processes a query."""

    CLASSIFYING = "classifying"
    PLANNING = "planning"
    TOOL_START = "tool_start"
    TOOL_SUCCESS = "tool_success"
    TOOL_FAILED = "tool_failed"
    SYNTHESIZING = "synthesizing"
    FINAL = "final"


@dataclass
class AssistantStageEvent:
    """A single staged-response event emitted during assistant processing."""

    stage: AssistantStage
    text: str
    tool_name: str | None = None
    elapsed_ms: int | None = None


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

_STAGE_STYLES: dict[AssistantStage, str] = {
    AssistantStage.CLASSIFYING: "dim cyan",
    AssistantStage.PLANNING: "bold cyan",
    AssistantStage.TOOL_START: "dim",
    AssistantStage.TOOL_SUCCESS: "green",
    AssistantStage.TOOL_FAILED: "red",
    AssistantStage.SYNTHESIZING: "dim cyan",
    AssistantStage.FINAL: "bold",
}


def stage_to_style(stage: AssistantStage) -> str:
    """Return the Rich markup style string for *stage*."""
    return _STAGE_STYLES[stage]


def format_stage_event(event: AssistantStageEvent) -> str:
    """Return a human-readable line for *event*.

    Tool stages include the tool name and optional elapsed time; progress
    stages return a fixed spinner-style string; FINAL returns ``event.text``.
    """
    stage = event.stage
    if stage is AssistantStage.TOOL_START:
        return f"⟳ {event.tool_name} running..."
    if stage is AssistantStage.TOOL_SUCCESS:
        return f"✓ {event.tool_name} success {event.elapsed_ms}ms"
    if stage is AssistantStage.TOOL_FAILED:
        return f"✗ {event.tool_name} failed {event.elapsed_ms}ms"
    if stage is AssistantStage.CLASSIFYING:
        return "⋯ classifying..."
    if stage is AssistantStage.PLANNING:
        return "⋯ planning..."
    if stage is AssistantStage.SYNTHESIZING:
        return "⋯ synthesizing..."
    # FINAL — return the answer text directly
    return event.text
