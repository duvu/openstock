# tui-terminal-rendering-integrity Specification Delta

## ADDED Requirements

### Requirement: TUI SHALL be the sole terminal-frame owner while active

When the full-screen Textual application is running, OpenStock application logging SHALL NOT write directly to terminal stdout or stderr outside Textual's rendering pipeline.

Intentional user-facing TUI content SHALL be rendered through Textual widgets and typed conversation or status models.

#### Scenario: A logger emits while the TUI is mounted

- **GIVEN** the logging surface is `tui`
- **AND** the Textual application is mounted
- **WHEN** an OpenStock logger emits an INFO, WARNING, or ERROR record
- **THEN** the record is written to the configured structured log file
- **AND** no OpenStock-owned log handler writes the record directly to stdout or stderr
- **AND** the Textual frame remains intact

#### Scenario: A command produces user-facing output

- **GIVEN** the TUI is active
- **WHEN** a command or assistant turn returns a result, warning, refusal, or error intended for the user
- **THEN** the result is rendered through the TUI presentation path
- **AND** diagnostic logging is not used as the primary user-facing rendering mechanism

### Requirement: Logging SHALL support explicit execution surfaces

The logging subsystem SHALL support explicit, typed execution surfaces with at least `cli`, `tui`, and `test` behavior.

#### Scenario: CLI surface is configured

- **WHEN** logging is configured for the `cli` surface
- **THEN** structured rotating file logging is enabled
- **AND** colored console diagnostics are enabled exactly once

#### Scenario: TUI surface is configured

- **WHEN** logging is configured for the `tui` surface
- **THEN** structured rotating file logging remains enabled
- **AND** the OpenStock-owned console/stderr handler is absent or disabled before Textual owns the terminal

#### Scenario: Test surface is configured

- **WHEN** logging is configured for the `test` surface
- **THEN** output behavior is deterministic and controllable by the test fixture
- **AND** direct console diagnostics are disabled by default

### Requirement: Logging reconfiguration SHALL be idempotent and ownership-safe

Repeated logging configuration SHALL reconcile OpenStock-owned handlers and listeners to the requested surface without duplicating output or deleting unrelated handlers.

#### Scenario: Logging transitions across surfaces

- **WHEN** one process configures the sequence `cli → tui → tui → cli`
- **THEN** exactly one OpenStock file pipeline is active after each transition
- **AND** TUI stages have no OpenStock console handler
- **AND** the final CLI stage has exactly one OpenStock console handler
- **AND** each emitted record is written at most once per configured destination

#### Scenario: A foreign handler exists

- **GIVEN** the root logger contains a handler not owned by OpenStock
- **WHEN** OpenStock reconciles its logging surface
- **THEN** the foreign handler is preserved
- **AND** only OpenStock-owned handlers and listeners are added, replaced, or removed

#### Scenario: An obsolete queue listener is replaced

- **WHEN** logging configuration requires replacing an OpenStock queue/file pipeline
- **THEN** the obsolete listener is stopped safely
- **AND** no orphan listener continues writing duplicate records

### Requirement: TUI logging failure SHALL fail without creating a competing terminal writer

If structured file logging cannot be initialized for TUI mode, the system SHALL NOT silently enable direct stderr logging as a fallback.

#### Scenario: TUI file handler initialization fails

- **WHEN** the configured TUI log path cannot be opened or initialized
- **THEN** the system records or returns a bounded initialization failure
- **AND** the TUI may render an in-app warning after mount
- **AND** no OpenStock diagnostic handler writes directly to terminal stderr while the TUI is active

### Requirement: Main workspace regions SHALL not overlap

The main TUI SHALL assign non-overlapping regions to status, main body, transcript, composer, footer, and optional TODO content.

#### Scenario: Default workspace is mounted

- **WHEN** the TUI is mounted at a supported viewport size
- **THEN** the output region ends at or above the composer region
- **AND** the composer ends at or above the visible footer region
- **AND** the output and TODO regions remain inside the main-body region

#### Scenario: Transcript content grows

- **WHEN** long or wrapped transcript content is appended
- **THEN** the transcript scrolls inside its RichLog region
- **AND** the Screen, main body, and output column do not scroll the complete application frame
- **AND** composer and footer positions remain structurally valid

### Requirement: The transcript SHALL be the sole scroll owner for conversation output

Conversation growth SHALL be handled by the transcript RichLog or equivalent bounded transcript widget.

#### Scenario: More transcript lines exist than fit the viewport

- **WHEN** conversation output exceeds the transcript region
- **THEN** the transcript widget provides scrolling
- **AND** the main application frame does not expand beyond the terminal
- **AND** transcript content does not render over the composer, footer, TODO rail, or status bar

### Requirement: Composer suggestions SHALL be bounded by terminal height

The responsive layout policy SHALL account for terminal height as well as terminal width when deciding how many suggestions may be shown.

#### Scenario: Slash suggestions open on a short terminal

- **GIVEN** the terminal is `80x20` or another compact-height viewport
- **WHEN** the user types `/`
- **THEN** the visible suggestion count is reduced to a compact limit
- **AND** a usable transcript region remains visible
- **AND** the input remains visible and usable
- **AND** the composer does not overlap the footer or output region

#### Scenario: Slash suggestions open on a tall terminal

- **GIVEN** the terminal has sufficient height
- **WHEN** the user types `/`
- **THEN** the configured full suggestion capacity may be shown
- **AND** all non-overlap invariants remain true

#### Scenario: Terminal size changes while suggestions are open

- **WHEN** the terminal is resized
- **THEN** the suggestion capacity is recomputed
- **AND** the current input value and command filtering state are preserved
- **AND** the resulting layout remains non-overlapping

### Requirement: Compact-height mode SHALL preserve essential interaction

When the terminal cannot fit all normal chrome and content, the TUI SHALL reduce optional content before making the primary input unusable.

#### Scenario: Footer cannot fit with minimum transcript and composer

- **WHEN** terminal height is below the configured compact threshold
- **THEN** the TUI may hide or compact the footer
- **AND** the composer remains visible
- **AND** the transcript retains its configured minimum usable height where physically possible
- **AND** essential shortcuts remain discoverable through `/help` or another bounded mechanism

### Requirement: TODO content SHALL remain bounded inside the main body

The TODO rail SHALL have an explicit scrolling or bounded truncation contract.

#### Scenario: A workspace has many TODO items

- **GIVEN** the TODO rail contains at least 50 tasks or warnings
- **WHEN** the TUI renders the rail
- **THEN** the rail region remains inside the main-body region
- **AND** TODO content scrolls, virtualizes, or truncates with an explicit indicator
- **AND** the rail does not alter composer or footer geometry

#### Scenario: TODO visibility is toggled

- **WHEN** the user shows or hides the TODO rail on a supported width
- **THEN** the output region is recomputed inside main-body
- **AND** composer focus is preserved
- **AND** no regions overlap

### Requirement: LogScreen SHALL fully own the active Textual screen

The F12 LogScreen SHALL render as an opaque, bounded screen and SHALL isolate input from the underlying application.

#### Scenario: LogScreen opens

- **WHEN** the user invokes the log-viewer action
- **THEN** LogScreen becomes the active screen
- **AND** it covers the underlying application with an opaque background
- **AND** its toolbar and log display remain inside the active screen region
- **AND** the log display owns scrolling for log records

#### Scenario: Printable keys are entered while LogScreen is active

- **GIVEN** LogScreen is active
- **WHEN** the user enters printable keys or filter-navigation keys
- **THEN** the underlying composer value is unchanged
- **AND** input is handled by LogScreen or ignored within LogScreen

#### Scenario: LogScreen closes

- **WHEN** the user presses `Esc`
- **THEN** LogScreen is popped
- **AND** the previous screen is restored
- **AND** the previous composer value and application state are preserved

#### Scenario: LogScreen opens on a narrow terminal

- **GIVEN** a narrow or short supported viewport
- **WHEN** LogScreen opens
- **THEN** level controls use a bounded responsive representation
- **AND** the toolbar does not overlap the log display
- **AND** the screen remains closable by keyboard

### Requirement: Geometry SHALL be validated using actual Textual regions

The regression suite SHALL inspect runtime widget regions rather than relying only on CSS-string assertions or display flags.

#### Scenario: Required viewport matrix is tested

- **WHEN** the headless TUI suite runs
- **THEN** it validates at least `80x20`, `100x24`, `120x30`, and `160x50`
- **AND** each viewport validates the default workspace
- **AND** each relevant viewport validates suggestions open
- **AND** each relevant viewport validates long transcript and TODO content

#### Scenario: Region intersection is detected

- **WHEN** any output, composer, footer, TODO, toolbar, or log-display region violates its containment invariant
- **THEN** the geometry test fails with the involved region coordinates

### Requirement: Terminal logging integrity SHALL be regression tested

The suite SHALL prove that TUI diagnostic logs are file-backed without direct terminal output.

#### Scenario: A log record is emitted in TUI surface

- **WHEN** a test emits a uniquely identified record after TUI logging is configured
- **THEN** captured stderr does not contain the record
- **AND** the structured log file contains the record exactly once

#### Scenario: A log record is emitted in CLI surface

- **WHEN** a test emits a uniquely identified record after CLI logging is configured
- **THEN** the configured console output contains the record exactly once
- **AND** the structured log file contains the record exactly once

### Requirement: Existing TUI behavior SHALL remain compatible

The rendering-integrity change SHALL preserve existing TUI behavior unrelated to the defect.

#### Scenario: Existing workflows run after the fix

- **WHEN** existing command routing, natural-language chat, structured answer rendering, artifact detail navigation, TODO toggling, and log filtering tests run
- **THEN** they continue to pass unless an accepted requirement explicitly updates their geometry or logging expectations

#### Scenario: Existing safety tests run after the fix

- **WHEN** research-only policy and safety tests run
- **THEN** no broker, order, account, portfolio, allocation, margin, transfer, or trading-execution capability is introduced

## MODIFIED Requirements

### Requirement: TUI research workflow presentation depends on rendering integrity

The `tui-research-workflow-polish` change SHALL treat terminal rendering integrity as a prerequisite for reliable composer-first research artifact presentation.

#### Scenario: Research workflow UI adds or expands content

- **WHEN** research workflow rendering adds tables, cards, drill-down output, status lines, or artifact detail content
- **THEN** it preserves the non-overlap and terminal-ownership requirements defined by this specification
- **AND** it does not add a direct terminal logging path outside Textual.