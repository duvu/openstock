# Proposal: Refactor TUI into an opencode-like chat-first workspace

## Summary

Refactor the OpenStock TUI from a multi-screen dashboard into an opencode-like terminal agent interface.

Target layout:

```text
+------------------------------------------------+
| Output / Conversation Stream                   |
|                                                |
| - Assistant answer                             |
| - Command result                               |
| - Tool trace                                   |
| - Warning / error                              |
| - Table / markdown / logs summary              |
|                                                |
+------------------------------------------------+
| > Ask, /command, /repair, /logs, /deploy ...   |
+------------------------------------------------+
```

The default TUI must have exactly two primary visible regions:

```text
1. OutputStream at the top
2. ComposerInput at the bottom
```

This is an OpenSpec-only change. It defines requirements for a future implementation PR; it does not implement the TUI refactor yet.

## Why

The current TUI still uses a multi-screen dashboard model:

```text
ContentSwitcher(main-workspace)
  - HomeScreen
  - WatchlistScreen
  - CommandScreen
  - AssistantScreen
  - RejectedScreen
  - QualityScreen
  - OutcomeScreen
  - LogScreen

ChatPanel(chat-panel)
  - RichLog(chat-log)
  - Input(chat-input)
```

This makes the TUI feel like a dashboard with a secondary chat panel, not a terminal AI agent workspace.

The desired UX is closer to opencode:

```text
single output stream
single composer input
inline tool traces
inline command results
inline errors/warnings
no separate command history pane
no separate command result pane
no screen switching as the primary workflow
```

## Problem statement

OpenStock should present one unified interaction surface. The user should type everything into one input box:

```text
natural language questions
slash commands
logs queries
repair commands
deploy commands
plan approval/cancellation
```

The result should render in the same output stream above the input. The user should not need to switch screens to perform common research, command, repair, logging, or deploy workflows.

## Goals

- Replace default multi-screen TUI workflow with a chat-first workspace.
- Keep exactly one visible input in the default TUI.
- Keep exactly one primary output/conversation stream in the default TUI.
- Route natural-language questions to ChatController.
- Route slash commands to CommandExecutor.
- Render command results, assistant answers, tool trace, errors, warnings, repair outputs, deploy outputs, and logs summaries inline.
- Preserve closed-loop observability logging for all TUI interactions.
- Reuse existing business logic; do not rewrite scoring, watchlist, repair, deploy, logs, or assistant domain logic.
- Keep old screens only as legacy/internal renderers if needed, not as the default workflow.

## Non-goals

- No pixel-perfect clone of opencode.
- No removal of business capabilities.
- No rewrite of the assistant, command executor, scoring, watchlist, repair, deploy, or logs subsystems.
- No change to the read-only research boundary.
- No bypass of closed-loop logging, repair, deploy, validation, or safety guardrails.
- No requirement to delete all legacy screen files in the first implementation.

## Scope

### New default layout

`vnalpha tui` SHALL compose only:

```text
OutputStream(id="output-stream")
ComposerInput(id="composer-input")
```

No `ContentSwitcher` SHALL be mounted in the default TUI path.

No `ChatPanel` SHALL be mounted as a secondary panel below a main workspace.

No `CommandScreen`, `CommandInput`, or `CommandResultPanel` SHALL be part of the default workflow.

### Input routing

The single composer input SHALL route:

```text
/command text      -> CommandExecutor
plain language    -> ChatController.handle_turn()
approve/cancel    -> ChatController pending plan action when applicable
/clear             -> clear visible OutputStream only
/logs ...          -> logs command behavior or CommandExecutor bridge
/repair ...        -> repair command behavior or CommandExecutor bridge
/deploy ...        -> deploy command behavior or CommandExecutor bridge
```

### Output rendering

OutputStream SHALL render:

```text
user input
assistant answer
assistant refusal
plan preview
plan approved/cancelled state
command result
tool trace event
error/warning
table/markup block
log summary
repair bundle path/status
deploy verification/promotion/rollback status
```

### Closed-loop observability

Every submitted TUI input SHALL produce observability events:

```text
TUI_INPUT_SUBMITTED
COMMAND_STARTED / COMMAND_SUCCEEDED / COMMAND_FAILED for slash commands
CHAT_TURN_STARTED / completed/refused/failed for natural-language turns
TOOL_CALL_* for tools
TUI_RENDER_ERROR or equivalent for render failures
```

Events SHALL include non-empty correlation IDs and preserve redaction-by-default behavior.

## Success criteria

This change is complete only when:

```text
- `vnalpha tui` default path mounts exactly one OutputStream and one ComposerInput.
- No ContentSwitcher is mounted in the default TUI path.
- No secondary ChatPanel is mounted below a main workspace.
- Only one Textual Input exists in the default DOM.
- Natural-language input routes to ChatController.
- Slash commands route to CommandExecutor.
- Command results render inline in OutputStream.
- Assistant answers render inline in OutputStream.
- Tool traces render inline in OutputStream.
- Errors/warnings render inline in OutputStream and are logged.
- /logs, /repair, and /deploy commands are supported from the same composer path or explicitly bridged.
- Closed-loop observability still records TUI interactions.
- Legacy screen-switching tests are updated or retired.
- New TUI tests prove the opencode-like layout and routing.
```

## Completion principle

Do not treat cosmetic rearrangement as sufficient. The implementation must change the default interaction model from multi-screen dashboard to single conversation workspace.
