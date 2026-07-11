# Proposal: Responsive TODO side panel for TUI

## Summary

Refactor the TUI layout to support an optional right-side TODO panel on desktop-sized terminals while preserving a compact single-column layout on narrow terminals such as tmux on a phone.

Target desktop layout:

```text
┌──────────────────────────────────────────────┬──────────────────────────┐
│ OutputStream                                  │ TODOs                    │
│ - assistant answers                           │ - active workspace tasks │
│ - command results                             │ - pending actions        │
│ - tool traces                                 │ - warnings/follow-ups    │
│ - data readiness                              │                          │
├──────────────────────────────────────────────┴──────────────────────────┤
│ ComposerInput                                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

Target narrow/mobile/tmux layout:

```text
┌──────────────────────────────────────────────┐
│ OutputStream                                  │
│                                              │
├──────────────────────────────────────────────┤
│ ComposerInput                                │
└──────────────────────────────────────────────┘
```

The TODO panel is secondary context UI. It must not reintroduce dashboard-style screen switching or a second input.

## Why

The workspace is becoming more agentic. Users need to see active tasks while continuing to type in the main composer.

Examples:

```text
- review FPT after auto data provisioning
- compare FPT/MWG/HPG
- generate shortlist after watchlist refresh
- compact workspace before starting new research
- fix data freshness warning
```

A desktop terminal has enough space for a right-side TODO rail. A phone/tmux terminal does not. The interface must adapt without breaking the interaction model.

## Goals

- Add a right-side `TodoPanel` for wide terminals.
- Hide or collapse `TodoPanel` automatically on narrow terminals.
- Maintain one primary `OutputStream`.
- Maintain one primary `ComposerInput`.
- Maintain exactly one Textual `Input` in default TUI.
- Preserve visual/style consistency with existing TUI blocks.
- Make TODO panel read-only by default; actions still go through the composer.
- Show active tasks, pending follow-ups, warnings, and workspace lifecycle reminders.
- Integrate with workspace context tasks when available.
- Provide fallback in-memory TODO source if workspace context runtime is not yet implemented.
- Add keyboard toggle to show/hide TODO panel on desktop.
- Persist user display preference where safe and useful.
- Add headless TUI tests for wide and narrow terminal behavior.

## Non-goals

- Do not create a separate command input inside the TODO panel.
- Do not create a second chat panel.
- Do not reintroduce `ContentSwitcher` or dashboard screens in the default workflow.
- Do not require mouse interaction.
- Do not make phone/tmux layout cramped.
- Do not duplicate full workspace context in the TODO panel.
- Do not make TODO items authoritative if workspace context has fresher state.

## Consistency principles

### Layout consistency

The main workflow remains:

```text
OutputStream + ComposerInput
```

On desktop, the TODO panel is a secondary side rail attached to the output area.

### Interaction consistency

All user actions are still typed in the composer:

```text
/context task add ...
/context task done ...
/todo add ...
/todo done ...
/compact
```

The panel only displays and highlights. It is not a new command surface.

### Visual consistency

The TODO panel should use the same typography, labels, border style, status vocabulary, and severity conventions as OutputStream/status bar.

### Responsive consistency

Behavior should be deterministic:

```text
wide terminal   -> TODO panel visible by default
narrow terminal -> TODO panel hidden/collapsed by default
manual toggle   -> allowed but never breaks the composer/output layout
```

## Proposed breakpoint policy

Initial defaults:

```text
show TODO panel when terminal width >= 120 columns
hide TODO panel when terminal width < 120 columns
minimum TODO panel width: 28 columns
preferred TODO panel width: 32 columns
maximum TODO panel width: 40 columns
```

This should be configurable later, but hard-coded defaults are acceptable for first implementation if tests cover them.

## Proposed components

```text
vnalpha/src/vnalpha/tui/widgets/todo_panel.py
vnalpha/src/vnalpha/tui/todo_source.py
vnalpha/src/vnalpha/tui/responsive_layout.py
```

Potential model:

```text
TodoItem
- id
- title
- status: open | active | blocked | done
- priority: p0 | p1 | p2 | p3
- source: workspace | command | system | inferred
- symbol
- date
- created_at
- updated_at
```

## Success criteria

This change is complete only when:

```text
- desktop-width TUI renders OutputStream + TodoPanel + ComposerInput
- narrow-width TUI hides TodoPanel and preserves OutputStream + ComposerInput
- resizing from wide to narrow hides TodoPanel
- resizing from narrow to wide restores TodoPanel unless user explicitly disabled it
- default DOM still contains exactly one Textual Input
- TODO panel has no input widget
- TODO panel does not use ContentSwitcher
- TODO panel renders workspace tasks or fallback tasks
- TODO panel shows empty state clearly
- TODO panel style is consistent with existing TUI blocks
- keyboard toggle works
- tests cover wide layout, narrow layout, resize, toggle, empty state, populated state, and layout regression
```

## Completion principle

Do not mark this complete by only adding a static panel. The implementation must be responsive, non-invasive, consistent with the opencode-like workspace, and tested on wide and narrow terminal sizes.
