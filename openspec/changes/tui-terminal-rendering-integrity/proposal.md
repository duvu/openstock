# Proposal: TUI Terminal Rendering Integrity

## Summary

Define a focused OpenSpec change that prevents OpenStock logs and responsive widgets from corrupting the Textual terminal frame.

The original rendering fix was superseded and completed through GitHub issues
#189–#192:

```text
[Bug] TUI log output corrupts the Textual frame and overlaps composer/widgets
```

The target behavior is:

```text
one full-screen Textual owner of terminal rendering
+ file-backed structured logs
+ bounded non-overlapping widget regions
```

This is an OpenSpec-only change. It does not implement runtime code.

## Motivation

The current TUI can show log text over the transcript, composer, footer, or other widgets. The visual symptom resembles an `OutputStream` overlay, but the source indicates two separate mechanisms:

1. OpenStock installs a root `StreamHandler` that writes directly to `stderr` before Textual starts. Those writes bypass Textual's rendering model while Textual owns the terminal.
2. The layout did not define strict height and overflow contracts for the main body, output stream, expandable composer suggestions, and inline F12 drawer.

These defects interact. Direct terminal writes can corrupt any Textual frame, while layout pressure on short terminals makes the corruption and clipping more visible.

This is not merely visual polish. A corrupted terminal frame can:

- obscure assistant output;
- make the active input difficult to read;
- hide warnings or approval state;
- misrepresent which widget has focus;
- make operators believe a command or assistant response changed unexpectedly;
- reduce trust in audit and recovery workflows.

## Current architecture findings

### Logging path

The CLI callback configures logging before command dispatch. The logging subsystem installs both:

- a queue-backed rotating JSON file handler; and
- a colored root `StreamHandler` that writes to terminal `stderr`.

The `tui` command then starts `VnAlphaApp` without switching the process to a file-only logging surface. The existing F12 log viewer already tails the structured log file, so direct console logs are redundant during full-screen TUI operation.

### Layout path

The main application composes:

```text
StatusBar
Horizontal main-body
  Vertical output-column
    OutputStream
  DebugLogDrawer (hidden by default)
ComposerInput
footer-hint
```

The output area uses `1fr`, but the containment hierarchy does not consistently establish `min-height: 0` and `overflow: hidden` boundaries.

The composer contains a 3-line input plus an auto-height suggestion panel that can request up to 12 additional lines. On short terminals, the requested height can exceed the viewport after status, footer, borders, and the minimum transcript region are included.

The superseding workspace removes the competing TODO rail. Task state remains
available through bounded commands and transcript results, while the inline F12
drawer has an explicit bounded body contract.

### Test gap

Existing tests verify mounting, focus, display flags, and selected CSS strings. They do not assert actual Textual regions or direct stderr silence while the TUI is active.

## Goals

- Introduce surface-aware logging behavior for `cli`, `tui`, and tests.
- Ensure TUI mode never writes OpenStock application logs directly to terminal stdout or stderr.
- Preserve rotating structured file logs and the F12 log viewer.
- Reconcile logging handlers idempotently instead of relying on a one-shot configured flag.
- Define one scrolling owner for the transcript region.
- Ensure the transcript, inline drawer, composer, and footer never overlap.
- Make command suggestions responsive to terminal height as well as width.
- Keep task state in bounded commands or transcript results without a competing rail.
- Make the inline F12 drawer bounded, keyboard-safe, redacted, and independently scrollable.
- Add geometry tests at representative terminal sizes.
- Preserve existing structured conversation messages, command routing, artifact navigation, and research-only safety boundaries.

## Non-goals

- No redesign of assistant or command business logic.
- No new research intents, tools, warehouse schemas, or research artifacts.
- No replacement of Textual with another UI framework.
- No reintroduction of a dashboard-first ContentSwitcher workflow.
- No second primary input surface.
- No broad command-palette redesign beyond the height bounds needed for rendering integrity.
- No broker, order, account, portfolio, allocation, margin, transfer, or trading-execution capability.

## Scope

### 1. Surface-aware logging

The logging API SHALL support an explicit execution surface.

Minimum surfaces:

```text
cli
  rotating file + colored stderr

tui
  rotating file only

test
  deterministic fixture-selected output
```

The implementation SHALL own and reconcile named OpenStock handlers without deleting unrelated third-party handlers.

### 2. TUI terminal ownership

After TUI mode is activated and before `VnAlphaApp.run()` owns the terminal:

- OpenStock logging SHALL NOT write directly to stdout or stderr.
- File logging SHALL remain active.
- The F12 viewer SHALL continue to read the same structured log file.
- Repeated logging configuration SHALL NOT duplicate handlers or queue listeners.

### 3. Main layout containment

The Screen, main body, output column, OutputStream, nested RichLog, inline drawer, composer, and footer SHALL have explicit size and overflow responsibilities.

The transcript RichLog SHALL own transcript scrolling. Parent layout containers SHALL NOT scroll the entire application frame.

### 4. Height-aware composer behavior

The responsive layout policy SHALL account for terminal width and terminal height.

The number of visible command suggestions SHALL be bounded so the TUI preserves:

- the status region;
- a usable transcript region;
- the input region;
- the footer or a documented compact-footer alternative.

### 5. Full-width transcript

Long TODO and warning content SHALL remain available through bounded commands
or transcript results. No competing task rail SHALL reduce the main transcript.

### 6. Inline F12 log drawer

The inline drawer SHALL:

- remain inside the bounded main workspace;
- constrain filter and log regions;
- retain independent scrolling;
- close via F12 or `Esc` without screen navigation;
- preserve composer focus/value and transcript scroll state;
- remain usable on narrow and short terminals.

### 7. Geometry and integrity validation

Headless tests SHALL inspect real Textual widget regions at minimum:

```text
80x20
100x24
120x30
160x50
```

The tests SHALL cover:

- default layout;
- suggestions open;
- long TODO-command transcript content;
- long wrapped transcript content;
- inline drawer open and closed;
- TUI logging with an emitted log event.

## Relationship to existing OpenSpecs

This change is deliberately separate from `tui-research-workflow-polish`.

`tui-research-workflow-polish` defines what research artifacts are rendered and how users drill into them. This change defines whether the terminal frame remains structurally correct while any content is rendered.

The research-workflow polish change SHOULD consume this change as a rendering-integrity prerequisite.

The change remains aligned with `openstock-four-phase-hardening` because it addresses runtime correctness, observability, and regression testing rather than adding a new product capability.

## Success criteria

This change is complete only when:

```text
- TUI mode has no OpenStock-owned stderr/stdout log handler.
- CLI mode retains expected console logging.
- CLI -> TUI -> TUI -> CLI logging reconfiguration is idempotent.
- Structured rotating file logs remain available in all supported surfaces.
- OutputStream, composer, and footer regions do not intersect.
- TODO state remains available without a competing rail.
- Suggestion expansion does not make the transcript/composer/footer overlap.
- The inline drawer stays bounded and preserves workspace input/scroll state.
- Geometry tests pass at all required viewport sizes.
- Existing TUI routing, structured message, artifact navigation, and safety tests pass.
```

## Product boundary

This change only hardens logging and TUI rendering integrity.

It SHALL NOT introduce or enable broker connectivity, order placement, account management, portfolio allocation, margin, transfer, or trading execution.
