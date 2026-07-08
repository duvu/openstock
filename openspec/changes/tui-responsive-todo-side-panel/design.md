# Design: Responsive TODO side panel

## Design objective

Add a responsive right-side TODO rail to the TUI without breaking the opencode-like workspace model.

The design must preserve:

```text
single primary OutputStream
single primary ComposerInput
exactly one Textual Input
composer remains the only command entry surface
```

## Target layouts

### Desktop/wide terminal

```text
Root
├── Status/Header strip             optional compact support region
├── MainBody horizontal
│   ├── OutputColumn
│   │   └── OutputStream
│   └── TodoPanel                   secondary side rail
├── ComposerInput                   primary input region
└── FooterHint                      optional compact support region
```

### Narrow/tmux/phone terminal

```text
Root
├── Status/Header strip             optional compact support region
├── OutputStream
├── ComposerInput
└── FooterHint                      optional compact support region
```

`TodoPanel` must not be mounted as a visible layout element on narrow terminals, or must be collapsed with zero width and not consume focus.

## Responsive policy

Add:

```text
vnalpha/src/vnalpha/tui/responsive_layout.py
```

Suggested API:

```python
@dataclass
class ResponsiveLayoutPolicy:
    todo_visible_min_width: int = 120
    todo_min_width: int = 28
    todo_preferred_width: int = 32
    todo_max_width: int = 40
    force_hide_under_min_width: bool = True

class ResponsiveLayoutController:
    def should_show_todo(self, terminal_width: int, user_pref: bool | None) -> bool: ...
    def todo_width(self, terminal_width: int) -> int: ...
```

Behavior:

```text
if terminal_width < todo_visible_min_width:
    hide TODO panel regardless of manual preference
else:
    show TODO panel unless user explicitly disabled it
```

Manual toggle persists preference only for wide mode. Narrow mode always protects usability.

## TODO data model

Add:

```text
vnalpha/src/vnalpha/tui/todo_source.py
```

Suggested model:

```python
@dataclass
class TodoItem:
    id: str
    title: str
    status: Literal["open", "active", "blocked", "done"] = "open"
    priority: Literal["p0", "p1", "p2", "p3"] = "p2"
    source: Literal["workspace", "command", "system", "fallback"] = "fallback"
    symbol: str | None = None
    date: str | None = None
    detail: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
```

Source interface:

```python
class TodoSource(Protocol):
    def load_items(self) -> list[TodoItem]: ...
```

Implement:

```text
FallbackTodoSource
WorkspaceTodoSource
CompositeTodoSource
```

### FallbackTodoSource

Provides empty state or minimal process hints when workspace context runtime is unavailable.

### WorkspaceTodoSource

Reads from `workspace_context` tasks when that package exists.

It should degrade gracefully if workspace context is not installed or not initialised.

### CompositeTodoSource

Merges tasks from workspace and system sources, deduplicating by stable id or title/source.

## TODO panel widget

Add:

```text
vnalpha/src/vnalpha/tui/widgets/todo_panel.py
```

Widget responsibilities:

```text
render title
render task groups
render empty state
render blocked/warning items distinctly
render compact item rows
refresh from TodoSource
never create a Textual Input
not take focus by default
```

Suggested rendering:

```text
TODOs
ACTIVE
  P0 Review FPT after fresh score
BLOCKED
  P1 VNINDEX benchmark stale
NEXT
  P2 Compact workspace
```

Empty state:

```text
No TODOs yet
Use /todo add "..." or /context task add "..."
```

## Commands

Add TODO commands if workspace context task commands are not yet available:

```text
/todo list
/todo add <text>
/todo done <id>
/todo block <id>
/todo clear-done
```

If `/context task` exists or is implemented first, `/todo` may be an alias over workspace context tasks.

Important: all edits happen via composer commands, not directly inside the panel.

## App integration

`VnAlphaApp` should:

```text
- instantiate ResponsiveLayoutController
- instantiate TodoSource
- mount TodoPanel only when wide enough or hide/collapse it when narrow
- update layout on resize
- expose action_toggle_todo_panel()
- keep ComposerInput focus after toggling
- refresh TodoPanel after relevant commands complete
```

Suggested keybinding:

```text
Ctrl+T toggle TODO panel
```

If conflict exists, choose another key and document it.

## Resize behavior

On resize:

```text
wide -> narrow:
    hide/collapse TodoPanel
    keep OutputStream and ComposerInput usable
    status/footer may show TODO hidden due to narrow terminal

narrow -> wide:
    restore TodoPanel unless user preference disabled it
    refresh TODO items
```

## Status/footer integration

Footer hint should mention:

```text
Ctrl+T TODOs
```

On narrow terminals:

```text
TODOs hidden: narrow terminal
```

## Styling consistency

Use existing semantic style vocabulary where available:

```text
status-ready
status-warning
status-error
block-title
muted
accent
```

Do not create an unrelated visual system.

Panel should use consistent borders, padding, labels, and severity badges with OutputStream/status bar.

## Layout consistency tests

Tests must assert:

```text
wide app has TodoPanel
narrow app hides TodoPanel
one OutputStream
one ComposerInput
one Textual Input
no ContentSwitcher
no secondary ChatPanel
TodoPanel has no Input
ComposerInput remains focus target
```

## Headless terminal width tests

Use Textual pilot/headless APIs where possible.

Required cases:

```text
width 140 -> TodoPanel visible
width 120 -> TodoPanel visible
width 119 -> TodoPanel hidden
width 80  -> TodoPanel hidden
resize 140 -> 80 hides
resize 80 -> 140 restores
manual toggle hides on wide
manual toggle cannot force visible on narrow
```

## TODO source tests

Required:

```text
FallbackTodoSource returns safe empty/list state
WorkspaceTodoSource degrades if workspace context unavailable
CompositeTodoSource merges and deduplicates
TodoPanel renders empty state
TodoPanel renders active/blocked/next groups
```

## Observability

Emit best-effort events:

```text
TUI_TODO_PANEL_VISIBLE
TUI_TODO_PANEL_HIDDEN
TUI_TODO_PANEL_TOGGLED
TUI_TODO_PANEL_REFRESHED
TUI_TODO_ITEM_ADDED
TUI_TODO_ITEM_UPDATED
```

Avoid logging full raw task text in audit events unless redacted. Prefer metadata:

```text
item_id
status
priority
source
symbol
title_length
```

## Documentation

Update:

```text
vnalpha/docs/tui-workspace.md
```

Add:

```text
responsive TODO panel behavior
desktop vs narrow terminal layout
breakpoint policy
Ctrl+T toggle
/todo commands or /context task alias
consistency constraints
```

## Validation

Implementation PR should run:

```text
make test-vnalpha
make lint-vnalpha
make verify-r4
openstock-verify --ci
```

Validation evidence should include headless TUI tests for both desktop-width and narrow/tmux-like widths.
