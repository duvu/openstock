# Proposal: TUI input history and operational polish

## Summary

Complete the opencode-like TUI experience by adding command/text input history navigation and refining the default terminal workspace into a production-grade research console.

Primary user requirements:

```text
1. User can press Up to recall previous input.
2. User can press Down to move forward through history.
3. History works for both slash commands and natural-language text.
4. TUI layout is cleaner, more polished, and operationally informative.
5. TUI shows useful runtime states such as ready, running, syncing data, building features, scoring, assistant thinking, tool running, warning, error, and disconnected service.
```

This is an OpenSpec-only change. Runtime implementation will be done in a follow-up PR.

## Why

The current TUI has moved toward an opencode-like layout with a single output stream and one composer input. That is the right interaction model, but the workflow is not yet complete.

A terminal-agent UI without input history is inefficient. Users expect to press Up to recover or edit previous commands. This is especially important for repeated stock research workflows such as:

```text
/explain FPT --date 2026-07-08
/explain MWG --date 2026-07-08
/compare FPT MWG HPG --date 2026-07-08
/logs errors --latest
/repair prepare --latest
```

The TUI also needs visible operational state so the user understands whether the system is idle, running a command, syncing market data, building features, scoring, waiting for LLM response, or blocked by an error.

## Problem statement

The default TUI should behave like a high-quality terminal research agent:

```text
single output stream
single composer input
keyboard history
inline command/assistant/tool output
runtime status bar
clear error/warning states
progress messages for long actions
compact but readable visual hierarchy
```

The user should not lose previously typed input, should not need to retype commands manually, and should be able to understand system state without reading logs.

## Goals

- Add in-session input history navigation.
- Optionally persist input history across app restarts with redaction-aware storage.
- Support Up/Down navigation in the composer.
- Preserve draft text while navigating history.
- Deduplicate consecutive identical inputs.
- Store both slash commands and natural-language text.
- Avoid storing empty input or whitespace-only input.
- Add optional history search or prefix search if feasible.
- Refine TUI visual structure while preserving exactly one primary output stream and one primary composer input.
- Add an operational status strip or header/footer area that does not violate the two-primary-region model.
- Show runtime states for command execution, chat, tool calls, auto data provisioning, warnings, errors, and service availability.
- Keep closed-loop observability for history navigation and operational state transitions.
- Add tests for keyboard behavior, rendering, status transitions, and persistence where implemented.

## Non-goals

- No return to multi-screen dashboard workflow.
- No separate command-history panel.
- No separate command-result panel.
- No second input widget.
- No deletion of audit logs when visible output is cleared.
- No broker/order/account/portfolio functionality.
- No requirement for pixel-perfect clone of opencode.
- No network calls solely to decorate the UI.

## Scope

### Input history

The TUI SHALL maintain a history of submitted input items:

```text
slash commands
natural-language prompts
chat-local commands
operational commands
```

Navigation:

```text
Up       -> previous history item
Down     -> next history item
Ctrl+P   -> previous history item, optional but recommended
Ctrl+N   -> next history item, optional but recommended
Esc      -> clear current draft or cancel pending plan according to current behavior
```

### TUI polish

The TUI SHALL remain opencode-like:

```text
OutputStream
ComposerInput
```

But may add small supporting regions that do not become primary work panes:

```text
StatusBar / HeaderStrip / FooterHint
```

These regions should be compact and operational, not separate screens.

### Operational states

The TUI SHALL expose states such as:

```text
IDLE
ROUTING_INPUT
COMMAND_RUNNING
CHAT_THINKING
TOOL_RUNNING
DATA_ENSURE_RUNNING
DATA_SYNCING
BUILDING_FEATURES
SCORING
READY
WARNING
ERROR
SERVICE_UNAVAILABLE
```

### Visual refinement

Improve readability through:

```text
consistent message blocks
clear user/assistant/system/tool labels
compact timestamps if useful
status badges
warning/error formatting
command result blocks
progress lines for long operations
footer keyboard hints
```

## Success criteria

This OpenSpec is complete only when a follow-up implementation proves:

```text
- Pressing Up recalls the previous submitted input.
- Pressing Up repeatedly walks backward through history.
- Pressing Down walks forward through history.
- Draft text is restored after leaving history navigation.
- Consecutive duplicate inputs are not added twice.
- Empty inputs are not added to history.
- History works for both slash commands and natural-language text.
- Default TUI still has only one primary composer input.
- Default TUI still has only one primary output stream.
- No separate command history/result panel is reintroduced.
- Runtime status is visible and changes during command/chat/tool/data-provisioning flows.
- Errors and warnings are visually distinct and logged.
- Auto data provisioning states are visible when `/explain` or assistant analysis triggers data ensure.
- Tests cover keyboard navigation, status state transitions, and default layout constraints.
```

## Completion principle

Do not mark this complete with a cosmetic CSS change. Completion requires real keyboard history behavior plus operational-state UI that makes the TUI usable as a serious terminal research workspace.
