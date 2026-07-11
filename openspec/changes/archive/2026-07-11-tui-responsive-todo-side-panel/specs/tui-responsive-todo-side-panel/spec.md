# Specification: Responsive TODO side panel

## ADDED Requirements

### Requirement: Desktop TUI shall show right-side TODO panel

The default TUI SHALL show a right-side TODO panel when terminal width is wide enough.

#### Scenario: Wide terminal shows TODO panel

- **GIVEN** the TUI is mounted with terminal width 140 columns
- **WHEN** layout is computed
- **THEN** `TodoPanel` SHALL be visible as a right-side rail
- **AND** `OutputStream` SHALL remain visible
- **AND** `ComposerInput` SHALL remain visible.

#### Scenario: Minimum desktop width shows TODO panel

- **GIVEN** the TUI is mounted with terminal width 120 columns
- **WHEN** layout is computed
- **THEN** `TodoPanel` SHALL be visible.

---

### Requirement: Narrow TUI shall hide TODO panel

The default TUI SHALL hide or collapse the TODO panel on narrow terminals such as tmux on a phone.

#### Scenario: Width below breakpoint hides TODO panel

- **GIVEN** the TUI is mounted with terminal width 119 columns
- **WHEN** layout is computed
- **THEN** `TodoPanel` SHALL be hidden or collapsed
- **AND** it SHALL NOT reduce usability of `OutputStream` or `ComposerInput`.

#### Scenario: Phone-like width hides TODO panel

- **GIVEN** the TUI is mounted with terminal width 80 columns
- **WHEN** layout is computed
- **THEN** `TodoPanel` SHALL be hidden or collapsed
- **AND** only the main output/composer workflow SHALL remain visible.

---

### Requirement: Layout shall remain consistent with opencode-like workspace

Adding TODO panel SHALL NOT regress the primary TUI model.

#### Scenario: One primary output stream exists

- **GIVEN** the default TUI is mounted
- **WHEN** DOM is inspected
- **THEN** exactly one primary `OutputStream` SHALL exist.

#### Scenario: One primary composer exists

- **GIVEN** the default TUI is mounted
- **WHEN** DOM is inspected
- **THEN** exactly one `ComposerInput` SHALL exist.

#### Scenario: One Textual Input exists

- **GIVEN** the default TUI is mounted
- **WHEN** Textual `Input` widgets are counted
- **THEN** exactly one Textual `Input` SHALL exist.

#### Scenario: TODO panel has no input

- **GIVEN** `TodoPanel` is visible
- **WHEN** its subtree is inspected
- **THEN** it SHALL contain no Textual `Input`.

#### Scenario: Dashboard switcher is not reintroduced

- **GIVEN** the default TUI is mounted
- **WHEN** DOM is inspected
- **THEN** no `ContentSwitcher` SHALL exist in the default path.

#### Scenario: Secondary chat panel is not reintroduced

- **GIVEN** the default TUI is mounted
- **WHEN** DOM is inspected
- **THEN** no secondary `ChatPanel` SHALL be mounted.

---

### Requirement: TODO panel shall be responsive to resize

The TUI SHALL update TODO visibility when terminal size changes.

#### Scenario: Wide to narrow resize hides panel

- **GIVEN** TUI starts at width 140 with TODO panel visible
- **WHEN** terminal width changes to 80
- **THEN** TODO panel SHALL hide or collapse
- **AND** composer focus SHALL remain usable.

#### Scenario: Narrow to wide resize restores panel

- **GIVEN** TUI starts at width 80 with TODO panel hidden
- **WHEN** terminal width changes to 140
- **THEN** TODO panel SHALL become visible unless user preference disabled it.

---

### Requirement: User shall be able to toggle TODO panel on wide terminals

The TUI SHALL provide a keyboard action to toggle TODO panel visibility on desktop-sized terminals.

#### Scenario: Toggle hides visible panel

- **GIVEN** terminal is wide enough
- **AND** TODO panel is visible
- **WHEN** user presses the TODO toggle key
- **THEN** TODO panel SHALL be hidden
- **AND** `ComposerInput` SHALL keep or regain focus.

#### Scenario: Toggle restores hidden panel on wide terminal

- **GIVEN** terminal is wide enough
- **AND** TODO panel was hidden by user preference
- **WHEN** user presses the TODO toggle key
- **THEN** TODO panel SHALL become visible.

#### Scenario: Toggle cannot force panel on narrow terminal

- **GIVEN** terminal width is below responsive breakpoint
- **WHEN** user presses the TODO toggle key
- **THEN** TODO panel SHALL remain hidden
- **AND** output/composer layout SHALL remain usable.

---

### Requirement: TODO panel shall render task items from a source abstraction

The TODO panel SHALL read items through a source interface rather than hard-coding storage.

#### Scenario: Fallback source is available

- **GIVEN** workspace task storage is unavailable
- **WHEN** TODO panel loads items
- **THEN** it SHALL render a safe empty state or fallback list without crashing.

#### Scenario: Workspace tasks render when available

- **GIVEN** workspace context tasks are available
- **WHEN** TODO panel loads items
- **THEN** it SHALL render workspace tasks as TODO items.

#### Scenario: Duplicate items are deduplicated

- **GIVEN** multiple sources return the same logical task
- **WHEN** composite source merges items
- **THEN** duplicates SHALL be removed by stable id or title/source.

---

### Requirement: TODO panel shall use consistent visual semantics

The TODO panel SHALL match the visual language of the main TUI.

#### Scenario: Empty state is clear

- **GIVEN** there are no TODO items
- **WHEN** panel renders
- **THEN** it SHALL show a concise empty state with a hint for adding tasks.

#### Scenario: Active and blocked tasks are distinct

- **GIVEN** TODO items include active and blocked statuses
- **WHEN** panel renders
- **THEN** active and blocked items SHALL be visually distinguishable using existing severity/status vocabulary where possible.

#### Scenario: Panel remains compact

- **GIVEN** TODO panel contains multiple tasks
- **WHEN** panel renders
- **THEN** it SHALL show compact rows and avoid copying large context blocks.

---

### Requirement: TODO edits shall go through the composer

The TODO panel SHALL be read-only by default. Task changes SHALL be performed through composer commands.

#### Scenario: Add TODO through command

- **GIVEN** TODO commands are implemented
- **WHEN** user submits `/todo add Review FPT`
- **THEN** a TODO item SHALL be added
- **AND** the TODO panel SHALL refresh.

#### Scenario: Complete TODO through command

- **GIVEN** TODO commands are implemented
- **WHEN** user submits `/todo done <id>`
- **THEN** the item status SHALL become done
- **AND** the TODO panel SHALL refresh.

#### Scenario: Context task alias is allowed

- **GIVEN** workspace context task commands are implemented instead of native TODO commands
- **WHEN** user submits `/context task add Review FPT`
- **THEN** the TODO panel SHALL reflect the new workspace task.

---

### Requirement: Footer or status shall disclose TODO panel behavior

The TUI SHALL provide a compact hint for TODO panel visibility and toggle.

#### Scenario: Wide footer shows toggle hint

- **GIVEN** terminal is wide enough
- **WHEN** footer/status hint is rendered
- **THEN** it SHOULD mention the TODO toggle key.

#### Scenario: Narrow footer may show hidden reason

- **GIVEN** terminal is narrow
- **WHEN** TODO panel is hidden by responsive policy
- **THEN** footer/status MAY show that TODOs are hidden due to narrow terminal.

---

### Requirement: TODO panel visibility shall be observable

The system SHALL emit best-effort observability events for TODO panel lifecycle.

#### Scenario: Panel becomes visible

- **GIVEN** TODO panel becomes visible
- **WHEN** visibility changes
- **THEN** `TUI_TODO_PANEL_VISIBLE` or equivalent SHALL be emitted.

#### Scenario: Panel becomes hidden

- **GIVEN** TODO panel becomes hidden
- **WHEN** visibility changes
- **THEN** `TUI_TODO_PANEL_HIDDEN` or equivalent SHALL be emitted.

#### Scenario: Panel refresh is logged

- **GIVEN** TODO panel refreshes from source
- **WHEN** refresh completes
- **THEN** `TUI_TODO_PANEL_REFRESHED` or equivalent SHOULD be emitted.

---

### Requirement: Documentation and validation shall prove responsive behavior

The implementation SHALL include docs and tests for desktop and narrow layouts.

#### Scenario: Documentation describes responsive behavior

- **GIVEN** implementation is complete
- **WHEN** docs are inspected
- **THEN** `vnalpha/docs/tui-workspace.md` SHALL describe desktop TODO panel behavior, narrow/tmux behavior, breakpoint policy, and toggle key.

#### Scenario: Headless tests cover desktop layout

- **GIVEN** tests run
- **THEN** they SHALL verify TODO panel is visible on desktop-width terminals.

#### Scenario: Headless tests cover narrow layout

- **GIVEN** tests run
- **THEN** they SHALL verify TODO panel is hidden on narrow/tmux-like terminals.

#### Scenario: Layout regression tests pass

- **GIVEN** tests run
- **THEN** they SHALL verify the one-output, one-composer, one-input consistency constraints.
