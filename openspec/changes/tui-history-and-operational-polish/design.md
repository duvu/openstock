# Design: TUI history and operational polish

## Design objective

Complete the opencode-like TUI by adding:

```text
1. shell-like input history
2. compact operational status UI
3. polished output rendering
4. progress/state feedback for long-running workflows
```

The default TUI must remain a single conversation workspace, not a dashboard.

## Architecture overview

```text
VnAlphaApp
├── RuntimeStatusBar       compact state strip, optional but recommended
├── OutputStream           primary output region
├── ComposerInput          primary input region
└── FooterHint             compact keybinding/help strip, optional

ComposerInput
└── InputHistory

TuiInputRouter
└── status callbacks / status context manager
```

Only `OutputStream` and `ComposerInput` are primary regions. Status/header/footer strips are allowed only as compact supporting UI.

## Input history design

### New component

Add:

```text
vnalpha/src/vnalpha/tui/input_history.py
```

Suggested class:

```python
class InputHistory:
    def __init__(self, *, max_items: int = 500): ...
    def push(self, text: str) -> None: ...
    def previous(self, current_draft: str) -> str | None: ...
    def next(self) -> str | None: ...
    def reset_navigation(self) -> None: ...
    def items(self) -> list[str]: ...
```

### Behavior

`push(text)`:

```text
- ignore empty or whitespace-only input
- strip trailing newline
- preserve internal spaces
- do not append consecutive duplicate input
- reset navigation pointer after push
- enforce max_items
```

`previous(current_draft)`:

```text
- if not already navigating, store current_draft
- return most recent history item
- repeated calls walk older items
- clamp at oldest item
```

`next()`:

```text
- move toward newer items
- when moving past newest item, restore stored draft
- then exit history navigation
```

### Persistence

Phase 1 may be in-session only.

If persistence is implemented, use a bounded, redaction-aware file or warehouse table:

```text
~/.local/share/vnalpha/tui_input_history.jsonl
```

Rules for persistent history:

```text
- default max persisted items: 500
- allow disable via config/env
- do not store empty inputs
- optionally skip inputs matching sensitive patterns
- do not store raw secrets/tokens/cookies
- do not confuse visible history with audit logs
```

## ComposerInput integration

`ComposerInput` should own one Textual Input and one `InputHistory` instance or receive it from `VnAlphaApp`.

Keyboard behavior:

```text
Up      -> set input to history.previous(current_input)
Down    -> set input to history.next()
Ctrl+P  -> same as Up, optional
Ctrl+N  -> same as Down, optional
Enter   -> submit and push input into history only after successful submission dispatch starts
Esc     -> clear current input or cancel pending plan via app/router behavior
```

If the composer later becomes multiline, Up/Down behavior should be conditional on cursor position. For the current single-line composer, Up/Down is history navigation.

## Runtime status design

Add compact status model:

```text
vnalpha/src/vnalpha/tui/runtime_status.py
```

Suggested states:

```python
class RuntimeState(str, Enum):
    IDLE = "IDLE"
    ROUTING_INPUT = "ROUTING_INPUT"
    COMMAND_RUNNING = "COMMAND_RUNNING"
    CHAT_THINKING = "CHAT_THINKING"
    TOOL_RUNNING = "TOOL_RUNNING"
    DATA_ENSURE_RUNNING = "DATA_ENSURE_RUNNING"
    DATA_SYNCING = "DATA_SYNCING"
    BUILDING_FEATURES = "BUILDING_FEATURES"
    SCORING = "SCORING"
    READY = "READY"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
```

Suggested model:

```python
@dataclass
class RuntimeStatus:
    state: RuntimeState
    label: str = ""
    detail: str = ""
    current_input: str | None = None
    started_at: datetime | None = None
    last_error: str | None = None
```

Add compact widget:

```text
vnalpha/src/vnalpha/tui/widgets/status_bar.py
```

The status bar should show one line:

```text
READY | target=2026-07-08 | data=ok | vnstock=unknown | model=configured
RUNNING /explain FPT | syncing OHLCV
ERROR | vnstock-service unavailable
```

## Status event mapping

### Input routing

```text
submit input      -> ROUTING_INPUT
slash command     -> COMMAND_RUNNING
plain language    -> CHAT_THINKING
completion        -> READY or WARNING
exception         -> ERROR
```

### Tool trace

```text
tool RUNNING      -> TOOL_RUNNING
tool SUCCESS      -> previous command/chat state or READY
tool FAILED       -> WARNING or ERROR depending severity
```

### Data provisioning

Map `DATA_ENSURE_*` events into status updates where possible:

```text
DATA_ENSURE_STARTED                    -> DATA_ENSURE_RUNNING
DATA_ENSURE_SYMBOL_OHLCV_SYNC_STARTED  -> DATA_SYNCING
DATA_ENSURE_BENCHMARK_SYNC_STARTED     -> DATA_SYNCING
DATA_ENSURE_CANONICAL_BUILD_STARTED    -> BUILDING_FEATURES or BUILDING_CANONICAL if separate state exists
DATA_ENSURE_FEATURE_BUILD_STARTED      -> BUILDING_FEATURES
DATA_ENSURE_SCORE_STARTED              -> SCORING
DATA_ENSURE_READY                      -> READY
DATA_ENSURE_PARTIAL                    -> WARNING
DATA_ENSURE_FAILED                     -> ERROR
```

If direct event subscription is not available, update status from known router/service call boundaries and output messages.

## OutputStream visual polish

Add standardized blocks:

```text
UserBlock
AssistantBlock
CommandBlock
ToolTraceBlock
DataEnsureBlock
WarningBlock
ErrorBlock
SystemBlock
```

Each block should have a consistent label and compact formatting.

Recommended display:

```text
You
  /explain FPT --date 2026-07-08

System · DATA
  Ensuring FPT data for 2026-07-08...
  OHLCV synced: 252 rows | features built | score ready

Assistant
  FPT score=0.72 class=WATCH_CANDIDATE ...

Warning
  Benchmark VNINDEX latest bar is 2026-07-05, target date is 2026-07-08.
```

Do not use exact color assertions in tests. Prefer semantic methods and stable text content.

## Footer/keybinding hints

Optional compact footer:

```text
Enter submit · Up/Down history · Ctrl+L clear · /help commands · Esc cancel/clear
```

Footer should not be a primary pane.

## Observability

Emit best-effort events:

```text
TUI_HISTORY_PUSHED
TUI_HISTORY_PREVIOUS
TUI_HISTORY_NEXT
TUI_HISTORY_DRAFT_RESTORED
TUI_STATUS_CHANGED
TUI_RENDER_BLOCK_WRITTEN
```

For privacy, do not log full raw input in history-navigation events unless existing redaction policy is applied. Prefer metadata:

```text
input_length
input_kind: slash_command | natural_language | chat_local
history_index
history_size
state_from
state_to
```

## Tests

### InputHistory unit tests

```text
push ignores empty
push deduplicates consecutive duplicate
max_items enforced
previous returns newest first
previous clamps at oldest
next returns newer items
next restores draft after newest
reset_navigation exits navigation
```

### ComposerInput tests

```text
one Textual Input exists
Enter submits and pushes history
Up recalls previous command
Up twice recalls older command
Down moves forward
Down restores draft
history works for natural language
history works for slash commands
empty input not stored
```

### Layout tests

```text
one OutputStream
one ComposerInput
one Textual Input
no ContentSwitcher
no secondary ChatPanel
no CommandScreen as default workflow
status/footer widgets, if present, are compact supporting widgets
```

### Status tests

```text
submitting slash command sets COMMAND_RUNNING then READY
submitting chat sets CHAT_THINKING then READY
tool trace RUNNING sets TOOL_RUNNING
router exception sets ERROR
DATA_ENSURE_* path updates status to data states
```

### Visual block tests

```text
show_user_input writes user block
show_command_result writes command block
show_error writes error block
show_warning writes warning block
show_trace_event writes tool block
show_data_ensure writes data block if implemented
```

## Documentation

Update:

```text
vnalpha/docs/tui-workspace.md
```

Add:

```text
- keyboard shortcuts
- input history behavior
- status states
- meaning of data provisioning statuses
- visible clear vs persisted audit/history
- troubleshooting for stuck ERROR/SERVICE_UNAVAILABLE
```

## Validation

Implementation PR should run:

```text
make test-vnalpha
make lint-vnalpha
make verify-r4
openstock-verify --ci
```

Validation evidence should include a headless TUI test proving Up/Down input history and status transition coverage.
