# Review: Current TUI vs opencode-like target

## Verdict

The current TUI does not yet match the requested opencode-like model.

Current state:

```text
multi-screen dashboard + persistent secondary chat panel
```

Target state:

```text
single conversation workspace + one composer input
```

## Current implementation shape

The current default app composes a main workspace and a separate chat panel:

```text
ContentSwitcher(id="main-workspace")
ChatPanel(id="chat-panel")
```

The main workspace contains multiple screens. ChatPanel contains its own log and input.

This produces at least three conceptual UI regions:

```text
1. main workspace / screen result area
2. chat log / secondary conversation history
3. chat input
```

`CommandScreen` has improved by merging command history and command result into one scrollable log, but it still remains a separate screen with a separate command input workflow.

## Mismatch with target UX

### 1. Default workflow is screen-switching, not conversation-first

The user currently navigates screens for watchlist, commands, assistant, rejected, quality, outcomes, and logs. This is useful for a dashboard but does not match the requested opencode-like interaction.

### 2. Chat is a secondary panel

ChatPanel is mounted below the main workspace, so chat feels like a helper panel rather than the whole interaction surface.

### 3. Command execution is not unified with chat output

CommandScreen shows command output in its own screen. Natural-language answers appear through ChatPanel. This creates two output paths instead of one stream.

### 4. Tests still encode old assumptions

Existing TUI tests assert screen switching and persistent ChatPanel behavior. These tests must be replaced or moved to legacy coverage.

## Desired user experience

The new TUI should work like this:

```text
User types: scan VN30 today
OutputStream renders assistant plan/result/tool trace.

User types: /scan
OutputStream renders command result.

User types: /logs errors --latest
OutputStream renders latest errors.

User types: /repair prepare --latest
OutputStream renders repair bundle path and summary.

User types: /deploy verify candidate-x
OutputStream renders verification status.
```

The user should not need to switch screens for the primary path.

## Implementation risks

### Risk: breaking existing business logic

The refactor should change presentation and routing, not rewrite domain functionality. ChatController and CommandExecutor should remain the core orchestration layers.

### Risk: losing rich tables

Current screens render tables and panels. The OutputStream must support markup/table rendering sufficiently to avoid losing information.

### Risk: losing observability

Every input and render failure must still participate in the file-based observability system.

### Risk: tests become brittle

DOM-level tests should assert the important layout contract:

```text
one OutputStream
one ComposerInput
one Textual Input
no ContentSwitcher in default path
no ChatPanel in default path
```

Avoid tests that depend on exact visual styling.

## Recommended target architecture

```text
vnalpha.tui.app.VnAlphaApp
  -> OutputStream
  -> ComposerInput
  -> TuiInputRouter
       -> ChatController
       -> CommandExecutor
       -> plan approve/cancel actions
```

Optional compatibility:

```text
legacy screens remain importable
legacy renderers can be reused
but legacy screens are not mounted by default
```

## Readiness estimate after implementation

Expected completion if the OpenSpec is implemented with tests:

```text
opencode-like layout:       90-95%
unified routing:            85-90%
closed-loop TUI logging:    85-90%
legacy dashboard removal:   80-90%
```

## Key open question

Should old dashboard screens remain behind a feature flag such as `vnalpha tui --legacy-dashboard`, or should they be fully retired from runtime? The first implementation should prefer keeping them importable but not mounted by default.
