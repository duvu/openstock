"""ChatContext — multi-turn context tracking for the vnalpha chat workspace.

Tracks the last known state of a research chat session so that natural-language
follow-up questions can reference entities from previous turns without the user
repeating them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ChatContext:
    """Mutable context object threaded through chat turns.

    All fields are optional so that an empty ``ChatContext()`` is always safe
    to construct and pass without blowing up downstream consumers.
    """

    chat_session_id: str | None = None
    target_date: str | None = None
    last_symbols: list[str] = field(default_factory=list)
    selected_symbol: str | None = None
    selected_rank: int | None = None
    last_watchlist_date: str | None = None
    last_command: str | None = None
    last_assistant_intent: str | None = None
    last_plan: str | None = None
    last_tool_outputs_summary: str | None = None


# ---------------------------------------------------------------------------
# Context updater
# ---------------------------------------------------------------------------

_SYMBOL_PATTERN = re.compile(r"\b([A-Z]{2,5})\b")


def update_context_from_command(
    ctx: ChatContext,
    command_text: str,
    result_text: str,
) -> None:
    """Update *ctx* in-place based on a completed slash-command turn.

    Always updates ``last_command``.  For ``/scan`` commands, also tries to
    extract ``last_watchlist_date`` and ``last_symbols`` from *result_text*.

    Parameters
    ----------
    ctx:
        The :class:`ChatContext` to mutate.
    command_text:
        The raw slash-command the user typed (e.g. ``"/scan 2026-07-07"``).
    result_text:
        The rendered output / summary string returned by the command.
    """
    ctx.last_command = command_text.strip()

    # For /scan commands: try to pull out a date and ticker symbols
    stripped = command_text.strip()
    first_word = stripped[1:].split()[0].lower() if stripped.startswith("/") and stripped[1:].split() else ""
    if first_word == "scan":
        # Extract ISO date from the command arguments
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", command_text)
        if date_match:
            ctx.last_watchlist_date = date_match.group(0)

        # Extract uppercase ticker symbols from result text (2–5 chars)
        symbols = _SYMBOL_PATTERN.findall(result_text)
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for s in symbols:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        if unique:
            ctx.last_symbols = unique


# ---------------------------------------------------------------------------
# Entity reference resolver
# ---------------------------------------------------------------------------

_FIRST_PHRASES = re.compile(
    r"\b(the first one|first one|first symbol|number one|#1|top one)\b",
    re.IGNORECASE,
)
_TOP_PHRASES = re.compile(
    r"\b(top candidate|top pick|best candidate|best pick|top stock)\b",
    re.IGNORECASE,
)
_THAT_PHRASES = re.compile(
    r"\b(that symbol|that stock|that ticker|this symbol|this stock|this ticker|the stock|the ticker)\b",
    re.IGNORECASE,
)


def resolve_entity_reference(ctx: ChatContext, text: str) -> str:
    """Replace fuzzy entity references in *text* with concrete symbols from *ctx*.

    - "the first one" / "first symbol" → ``last_symbols[0]`` if available
    - "top candidate" / "top pick" → ``selected_symbol`` if available
    - "that symbol" / "that stock" / "that ticker" → ``selected_symbol`` if available

    Returns the original *text* unchanged when no replacement can be made.
    """
    result = text

    # Replace "the first one" style references
    first_sym = ctx.last_symbols[0] if ctx.last_symbols else None
    if first_sym:
        result = _FIRST_PHRASES.sub(first_sym, result)

    # Replace "top candidate" / "that symbol" style references
    sel = ctx.selected_symbol
    if sel:
        result = _TOP_PHRASES.sub(sel, result)
        result = _THAT_PHRASES.sub(sel, result)

    return result


# ---------------------------------------------------------------------------
# Prompt prefix builder
# ---------------------------------------------------------------------------


def build_context_prompt_prefix(ctx: ChatContext) -> str:
    """Return a short one-line context summary to prepend to LLM prompts.

    Returns an empty string ``""`` when the context carries no useful state,
    so callers can safely check ``if prefix: ...`` before prepending.

    Example output::

        Context: date=2026-07-07, symbols=[VNM,VCB], selected=VNM
    """
    parts: list[str] = []

    if ctx.target_date:
        parts.append(f"date={ctx.target_date}")
    elif ctx.last_watchlist_date:
        parts.append(f"date={ctx.last_watchlist_date}")

    if ctx.last_symbols:
        syms = ",".join(ctx.last_symbols[:10])  # cap at 10 to avoid huge prompts
        parts.append(f"symbols=[{syms}]")

    if ctx.selected_symbol:
        parts.append(f"selected={ctx.selected_symbol}")

    if not parts:
        return ""

    return "Context: " + ", ".join(parts) + "\n"
