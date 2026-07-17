# Design: TUI Terminal Rendering Integrity

## 1. Design objective

The TUI must have one authoritative owner of terminal rendering.

```text
application/domain events
        ↓
Textual widgets and screens
        ↓
terminal frame
```

OpenStock log handlers must not create a second terminal-output path while the full-screen TUI is active.

The layout must also establish one owner for each region:

```text
status bar      -> fixed status region
main body       -> bounded flexible region
output RichLog  -> transcript scrolling and task results
composer        -> bounded input and suggestions
footer          -> fixed or compact footer region
inline drawer   -> bounded filtered-log scrolling inside main body
```

## 2. Root cause model

The observed overlap is treated as two independent failure classes.

### 2.1 Terminal-frame corruption

A root `StreamHandler` writes to `stderr` after Textual has entered application mode. The bytes reach the terminal without passing through Textual's compositor.

This may overwrite any current row, including the composer, footer, borders, or modal content.

### 2.2 Layout overflow and clipping

Children request more vertical space than is available. The application depends on implicit container overflow behavior, causing one or more of:

- parent-screen scrolling;
- clipped transcript;
- composer or footer movement outside the viewport;
- border collisions;
- visually ambiguous modal screens.

The implementation must fix both classes. CSS changes alone cannot prevent direct stderr corruption, and disabling stderr alone cannot guarantee layout integrity on short terminals.

## 3. Surface-aware logging

### 3.1 Public contract

Introduce an explicit logging surface:

```python
from enum import Enum


class LogSurface(str, Enum):
    CLI = "cli"
    TUI = "tui"
    TEST = "test"


def configure_logging(
    level: str | None = None,
    log_path: Path | str | None = None,
    *,
    surface: LogSurface | str = LogSurface.CLI,
) -> None:
    ...
```

The exact names may vary, but the surface must be explicit and typed.

### 3.2 Handler ownership

Every OpenStock-owned handler SHALL have a stable identity.

Suggested names:

```text
vnalpha-queue
vnalpha-file
vnalpha-console
```

The configuration service SHALL:

1. inspect current root handlers;
2. preserve handlers not owned by OpenStock;
3. add, replace, or remove OpenStock-owned handlers to match the requested surface;
4. ensure only one active queue listener for the configured file path;
5. stop obsolete listeners before discarding them;
6. apply the selected log level consistently;
7. remain safe when called repeatedly.

The existing `_CONFIGURED: bool` gate is insufficient because it cannot represent a surface transition.

### 3.3 Surface matrix

| Surface | File log | Console stderr | Intended use |
|---|---:|---:|---|
| `cli` | yes | yes | conventional command output and diagnostics |
| `tui` | yes | no | full-screen Textual application |
| `test` | configurable | no by default | deterministic capture and assertions |

Application commands must continue to communicate user results through Typer/Rich command output. Disabling the logging console handler must not suppress intentional command output.

### 3.4 CLI integration

The root callback may configure the initial CLI surface:

```python
configure_logging(surface=LogSurface.CLI)
```

Immediately before Textual starts:

```python
configure_logging(surface=LogSurface.TUI)
VnAlphaApp(date=date).run()
```

The second call must remove the previously installed OpenStock console handler.

### 3.5 File log compatibility

TUI surface changes SHALL NOT change the canonical log path or JSON record format.

The inline F12 drawer must continue to tail the same file. Existing rotation limits remain unless separately changed.

### 3.6 Failure behavior

If file logging cannot be initialized in TUI mode:

- the system must not silently fall back to direct terminal stderr logging;
- the TUI may show a bounded in-app warning after mounting;
- the failure must not create a competing terminal writer.

## 4. Main layout containment

### 4.1 Region hierarchy

The layout remains composer-first:

```text
Screen vertical
├── StatusBar fixed
├── main-body flexible and contained
│   ├── output-column flexible and contained
│   │   └── OutputStream
│   │       └── RichLog transcript scroll owner
│   └── DebugLogDrawer bounded and hidden by default
├── ComposerInput bounded
└── footer-hint fixed or compact-hidden
```

No additional primary input or dashboard switcher is introduced.

### 4.2 Containment rules

The implementation SHOULD use equivalent rules to:

```css
Screen {
    layout: vertical;
    overflow: hidden;
}

#main-body {
    height: 1fr;
    min-height: 0;
    overflow: hidden;
}

#output-column {
    height: 1fr;
    min-height: 0;
    overflow: hidden;
}

OutputStream {
    height: 1fr;
    min-height: 0;
    overflow: hidden;
}

OutputStream > RichLog {
    height: 1fr;
    min-height: 0;
}
```

The normative requirement is the resulting ownership and non-overlap, not exact CSS spelling.

### 4.3 Scroll ownership

The transcript RichLog is the sole owner of transcript scrolling.

The Screen, `main-body`, and `output-column` must not scroll the complete application layout in response to transcript growth.

The composer and footer remain anchored below `main-body`.

### 4.4 Region invariants

At every supported viewport size:

```python
output.region.bottom <= composer.region.y
composer.region.bottom <= footer.region.y
output.region.bottom <= main_body.region.bottom
drawer.region.bottom <= main_body.region.bottom
```

When the footer is intentionally hidden in compact-height mode, the composer must remain inside the Screen and below the main body.

## 5. Responsive height policy

### 5.1 Current limitation

The existing responsive policy primarily considers width. Suggestion capacity is effectively fixed and can consume most of a short viewport.

### 5.2 Proposed policy

Extend the controller to accept both width and height.

Example model:

```python
@dataclass(frozen=True, slots=True)
class ResponsiveLayoutPolicy:
    todo_visible_min_width: int = 120
    todo_min_width: int = 28
    todo_preferred_width: int = 32
    todo_max_width: int = 40

    compact_height: int = 24
    medium_height: int = 32
    compact_suggestion_limit: int = 4
    medium_suggestion_limit: int = 6
    full_suggestion_limit: int = 10
    footer_hidden_below_height: int = 20
```

Example controller API:

```python
def suggestion_limit(self, terminal_width: int, terminal_height: int) -> int:
    ...


def show_footer(self, terminal_width: int, terminal_height: int) -> bool:
    ...
```

The exact threshold values are configuration defaults and may be adjusted through tests.

### 5.3 Composer API

ComposerInput should accept an updated limit without rebuilding its command registry:

```python
def set_suggestion_limit(self, limit: int) -> None:
    self._max_suggestions = max(1, limit)
    self._render_suggestions(current_value)
```

Mount and resize paths update the limit.

### 5.4 Minimum usable transcript

Suggestion expansion must preserve a minimum usable transcript height. The policy may reduce suggestion count or hide the footer before allowing the transcript to collapse below that minimum.

## 6. Full-width transcript

The main body contains one authoritative full-width transcript. TODO items and
warnings render through bounded commands or transcript results; no competing
right rail is mounted. This keeps transcript width, composer geometry, focus,
and scroll ownership stable across task-state changes.

## 7. Inline log drawer design

The drawer is mounted once inside `main-body`, hidden by default, and toggled by
F12. It never pushes or pops a screen. Its bounded record model is shared by
rendering and `/copy logs`, applies control-sequence and credential sanitization,
and preserves complete identifiers at compact widths.

When visible, the transcript and drawer share only the flexible main-body
height. The composer and footer remain anchored. F12 or Escape hides the drawer
and restores composer focus, value, and transcript scroll position.

### 7.4 Record bounds

The log viewer currently accumulates all parsed records in memory. A bounded record policy SHOULD be added or explicitly deferred with a follow-up. Rendering-integrity acceptance does not require full log pagination, but the implementation must avoid making overlap worse through unbounded widget growth.

## 8. Test architecture

### 8.1 Geometry helper

Create a reusable assertion helper:

```python
def assert_workspace_regions(app) -> None:
    output = app.query_one("#output-stream")
    composer = app.query_one("#composer-input")
    main = app.query_one("#main-body")
    footer = app.query_one("#footer-hint")

    assert output.region.bottom <= composer.region.y
    assert output.region.bottom <= main.region.bottom
    if footer.display:
        assert composer.region.bottom <= footer.region.y
```

If borders make direct child coordinates preferable, use the precise region relationship established by the final widget hierarchy. The invariant remains no intersection.

### 8.2 Viewport matrix

Run headless pilot tests at:

```text
80x20
100x24
120x30
160x50
```

### 8.3 State matrix

For every relevant viewport, cover:

- default app;
- slash suggestions open;
- long wrapping transcript;
- long TODO command results;
- router busy state;
- inline drawer open and closed.

### 8.4 Logging integrity

Tests must verify:

```text
surface=cli -> event appears on stderr and in file
surface=tui -> event absent from stderr and present in file
surface=tui repeated -> no duplicate handlers/listeners
cli -> tui -> tui -> cli -> expected output restored exactly once
```

A TUI pilot test should emit a log event while the app is mounted and verify no direct terminal output is captured.

### 8.5 Input isolation

With the inline drawer active:

1. capture underlying composer value;
2. send printable keys;
3. assert composer value is unchanged;
4. press Esc;
5. assert the drawer is hidden without screen navigation.

## 9. Observability

Surface transitions may emit bounded metadata:

```text
LOGGING_SURFACE_CONFIGURED
surface=tui
file_enabled=true
console_enabled=false
```

Do not log raw handler representations, paths containing secrets, or application content.

Layout tests provide the primary evidence; production layout should not emit high-volume resize logs by default.

## 10. Backward compatibility

- `configure_logging()` without an explicit surface retains CLI-compatible behavior.
- Existing canonical log files remain readable by the inline drawer.
- Existing command output remains separate from diagnostic logging.
- Existing TUI public imports and structured conversation models remain intact.
- Existing shortcuts remain unless they conflict with inline-drawer input isolation.
- Existing research-only policy is unchanged.

## 11. Rollout strategy

Recommended implementation order:

```text
1. logging surface model and tests
2. CLI/TUI integration
3. main layout containment and geometry tests
4. height-aware suggestion policy
5. full-width transcript containment
6. inline drawer containment and keyboard isolation
7. full focused regression suite and manual terminal QA
```

The stderr fix should land before or in the same implementation PR as geometry fixes. Shipping only the CSS portion leaves terminal corruption possible.

## 12. Validation evidence

The implementation PR must attach:

- focused Ruff output;
- focused TUI pytest output;
- handler transition test output;
- viewport geometry matrix result;
- manual QA notes at one short and one wide terminal size;
- confirmation that TUI log events remain visible in the inline F12 drawer;
- confirmation that non-TUI commands retain expected console behavior.
