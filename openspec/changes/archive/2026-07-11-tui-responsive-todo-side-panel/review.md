# Review: Responsive TODO side panel

## Verdict

A right-side TODO panel is useful, but only if it remains a secondary context rail. It must not break the current opencode-like terminal flow.

Correct target:

```text
wide screen:   OutputStream + right TODO rail + ComposerInput
narrow screen: OutputStream + ComposerInput only
```

Incorrect target:

```text
multi-pane dashboard
second input
separate task manager app inside the TUI
fixed layout that breaks phone/tmux use
```

## Main critique

### 1. Do not regress to dashboard layout

Previous refactors moved the TUI away from multi-screen dashboard behavior. The TODO panel must not reintroduce that pattern.

The panel should be a side rail, not a primary workspace.

### 2. TODO panel must be read-only first

Editing tasks directly inside the panel would require focus management, cursor behavior, selection state, and maybe another input. That increases complexity and risks violating the single-composer model.

Use composer commands first:

```text
/todo add "Review FPT after data sync"
/todo done <id>
/context task add ...
/context task done ...
```

### 3. Desktop and phone behavior must be explicitly tested

The main requirement is responsive behavior. A static CSS panel is not enough.

Need tests for:

```text
width >= 120 -> panel visible
width < 120  -> panel hidden
resize wide -> narrow -> hidden
resize narrow -> wide -> restored
```

### 4. Do not duplicate workspace context

The panel should display a curated short list, not the whole workspace context.

Good:

```text
P0 Review FPT after fresh score
P1 Build shortlist for banking sector
Blocked VNINDEX benchmark stale
```

Bad:

```text
full transcript
large tables
raw tool traces
complete compact.md
```

### 5. Data source must be abstracted

The TODO panel should not directly depend on one storage implementation. It should consume a provider interface:

```text
TodoSource.load_items() -> list[TodoItem]
```

That source can later read from workspace context, command state, or persisted task files.

### 6. Manual toggle must not fight responsive rules

User may toggle the panel manually on desktop. But on very narrow terminals, forcing the panel visible should not make the composer unusable.

Recommended policy:

```text
narrow terminal hard-hides panel regardless of manual preference
wide terminal respects manual preference
```

### 7. Consistency must be enforced by tests

The user explicitly requires consistency. Add layout regression tests that fail if:

```text
second Textual Input appears
ContentSwitcher returns
ChatPanel returns as secondary panel
default TUI mounts command screen by default
TodoPanel consumes primary focus by default
```

## Design ideas

### Idea 1: TODO item categories

Render items in groups:

```text
Active
Blocked
Next
Done recently
```

### Idea 2: Workspace-derived tasks

When workspace context runtime exists, map workspace tasks into TODO items:

```text
WorkspaceTask -> TodoItem
```

### Idea 3: System-generated follow-ups

System may add TODOs from important warnings:

```text
- benchmark stale
- candidate score missing
- workspace dirty, compact recommended
- data ensure partial
```

### Idea 4: Compact badges

Use short badges:

```text
P0
P1
ACTIVE
BLOCKED
DATA
CTX
```

### Idea 5: Footer hint

When panel is hidden because terminal is narrow, footer/status can show:

```text
TODOs hidden: terminal too narrow
```

### Idea 6: Toggle key

Recommended key:

```text
Ctrl+T -> toggle TODO panel
```

If conflict exists, choose another key and document it.

### Idea 7: Empty state

Empty state should be helpful:

```text
No TODOs yet
Use /todo add "..." or /context task add "..."
```

## MVP recommendation

MVP should implement:

```text
TodoItem model
TodoSource interface
FallbackTodoSource
WorkspaceTodoSource adapter if workspace_context exists
TodoPanel widget
ResponsiveLayout policy
Ctrl+T toggle
wide/narrow behavior
docs
tests
```

Defer:

```text
mouse actions
inline edit
drag/drop
multi-select
calendar/deadline workflow
remote sync
```

## Risks

### Risk: narrow terminals become unusable

Mitigation: hard-hide panel below breakpoint and test small widths.

### Risk: panel duplicates context

Mitigation: only show short curated TODO items, max visible count, scroll if needed.

### Risk: inconsistent task state

Mitigation: source interface and explicit refresh events.

### Risk: focus bugs

Mitigation: read-only panel, composer keeps focus by default.

### Risk: visual inconsistency

Mitigation: define semantic classes and reuse existing status vocabulary.
