# tui-history-operational-polish Specification

## Purpose
TBD - created by archiving change tui-history-and-operational-polish. Update Purpose after archive.
## Requirements
### Requirement: Composer shall support input history navigation

The default TUI composer SHALL allow users to recall previously submitted slash commands and natural-language text.

#### Scenario: Up recalls previous input

- **GIVEN** the user has submitted `/explain FPT`
- **AND** the composer is empty
- **WHEN** the user presses Up
- **THEN** the composer value SHALL become `/explain FPT`.

#### Scenario: Repeated Up walks older inputs

- **GIVEN** the user has submitted `/explain FPT` then `/compare FPT MWG`
- **WHEN** the user presses Up once
- **THEN** the composer SHALL show `/compare FPT MWG`
- **WHEN** the user presses Up again
- **THEN** the composer SHALL show `/explain FPT`.

#### Scenario: Down walks newer inputs

- **GIVEN** the user is viewing an older history item
- **WHEN** the user presses Down
- **THEN** the composer SHALL show the next newer history item.

#### Scenario: Down restores draft after newest history item

- **GIVEN** the user typed `/explain HPG` but has not submitted it
- **AND** the user presses Up to browse history
- **WHEN** the user presses Down past the newest history item
- **THEN** the composer SHALL restore `/explain HPG`.

#### Scenario: Empty input is not stored

- **GIVEN** the composer contains whitespace only
- **WHEN** the user submits
- **THEN** that value SHALL NOT be added to history.

#### Scenario: Consecutive duplicate input is not stored twice

- **GIVEN** the most recent history entry is `/explain FPT`
- **WHEN** the user submits `/explain FPT` again immediately
- **THEN** history SHALL contain only one consecutive `/explain FPT` entry.

---

### Requirement: History shall work for all composer input types

History SHALL store both slash commands and natural-language prompts.

#### Scenario: Slash commands are stored

- **GIVEN** the user submits `/logs errors --latest`
- **WHEN** the user presses Up later
- **THEN** `/logs errors --latest` SHALL be recallable.

#### Scenario: Natural-language text is stored

- **GIVEN** the user submits `đánh giá FPT hôm nay`
- **WHEN** the user presses Up later
- **THEN** `đánh giá FPT hôm nay` SHALL be recallable.

#### Scenario: Chat-local commands are stored

- **GIVEN** the user submits `/plan on`
- **WHEN** the user presses Up later
- **THEN** `/plan on` SHALL be recallable.

---

### Requirement: Default TUI layout shall remain opencode-like

The history and polish work SHALL NOT regress the default layout back into a dashboard.

#### Scenario: Default layout has one primary output stream

- **GIVEN** the default TUI is mounted
- **WHEN** the DOM is inspected
- **THEN** exactly one primary `OutputStream` SHALL exist.

#### Scenario: Default layout has one primary composer input

- **GIVEN** the default TUI is mounted
- **WHEN** Textual `Input` widgets are counted
- **THEN** exactly one composer input SHALL exist.

#### Scenario: Default layout has no dashboard switcher

- **GIVEN** the default TUI is mounted
- **WHEN** the DOM is inspected
- **THEN** no `ContentSwitcher` SHALL exist in the default path.

#### Scenario: Default layout has no secondary chat panel

- **GIVEN** the default TUI is mounted
- **WHEN** the DOM is inspected
- **THEN** no secondary `ChatPanel` SHALL be mounted below the output stream.

#### Scenario: No separate command history pane is added

- **GIVEN** input history exists
- **WHEN** the TUI is rendered
- **THEN** history SHALL be navigated through the composer value
- **AND** no separate command history panel SHALL be shown.

---

### Requirement: TUI shall expose compact operational status

The TUI SHALL show the current runtime state in a compact, non-primary status widget or equivalent.

#### Scenario: Ready state is visible

- **GIVEN** the TUI has completed startup
- **WHEN** no command or chat turn is running
- **THEN** the status SHALL show `READY` or equivalent.

#### Scenario: Command running state is visible

- **GIVEN** the user submits a slash command
- **WHEN** command execution begins
- **THEN** the status SHALL show `COMMAND_RUNNING` or equivalent.

#### Scenario: Chat thinking state is visible

- **GIVEN** the user submits natural-language text
- **WHEN** the assistant flow begins
- **THEN** the status SHALL show `CHAT_THINKING` or equivalent.

#### Scenario: Tool running state is visible

- **GIVEN** a tool trace event reports `RUNNING`
- **WHEN** the event is rendered
- **THEN** the status SHALL show the running tool name or equivalent.

#### Scenario: Error state is visible

- **GIVEN** command routing, chat execution, rendering, or data provisioning fails
- **WHEN** the failure is handled
- **THEN** the status SHALL show `ERROR` or equivalent
- **AND** the output stream SHALL show a clear error block.

---

### Requirement: Data provisioning operational states shall be visible

Auto data provisioning triggered by analysis workflows SHALL expose visible states in the TUI.

#### Scenario: Data ensure starts

- **GIVEN** `/explain FPT` triggers data provisioning
- **WHEN** ensure-data starts
- **THEN** the status SHALL show `DATA_ENSURE_RUNNING` or equivalent.

#### Scenario: OHLCV sync starts

- **GIVEN** symbol OHLCV is missing
- **WHEN** sync starts
- **THEN** the status SHALL show `DATA_SYNCING` or equivalent with the symbol.

#### Scenario: Feature build starts

- **GIVEN** feature snapshot is missing
- **WHEN** feature build starts
- **THEN** the status SHALL show `BUILDING_FEATURES` or equivalent.

#### Scenario: Scoring starts

- **GIVEN** candidate score is missing
- **WHEN** scoring starts
- **THEN** the status SHALL show `SCORING` or equivalent.

#### Scenario: Data ensure completes partially

- **GIVEN** provisioning ends with warnings
- **WHEN** output is rendered
- **THEN** the status SHALL show `WARNING` or equivalent
- **AND** OutputStream SHALL include the warning details.

---

### Requirement: Output stream shall use consistent semantic blocks

The output stream SHALL render major message types in a consistent, readable structure.

#### Scenario: User input block is rendered

- **GIVEN** the user submits input
- **WHEN** it is appended to OutputStream
- **THEN** it SHALL be rendered as a user block or equivalent.

#### Scenario: Assistant message block is rendered

- **GIVEN** assistant output is produced
- **WHEN** it is appended to OutputStream
- **THEN** it SHALL be rendered as an assistant block or equivalent.

#### Scenario: Command result block is rendered

- **GIVEN** a command returns a result
- **WHEN** it is appended to OutputStream
- **THEN** it SHALL be rendered as a command result block or equivalent.

#### Scenario: Warning block is rendered

- **GIVEN** a command/chat/data operation returns warnings
- **WHEN** OutputStream renders the result
- **THEN** warnings SHALL be visually distinct.

#### Scenario: Error block is rendered

- **GIVEN** an error occurs
- **WHEN** OutputStream renders the error
- **THEN** the error SHALL be visually distinct and concise.

---

### Requirement: Footer or hint text shall document keybindings

The TUI SHALL provide compact keybinding hints.

#### Scenario: History keybinding is visible

- **GIVEN** the TUI is mounted
- **WHEN** the footer or hint strip is rendered
- **THEN** it SHALL mention Up/Down history or equivalent.

#### Scenario: Clear keybinding is visible

- **GIVEN** the TUI is mounted
- **WHEN** the footer or hint strip is rendered
- **THEN** it SHALL mention Ctrl+L clear or equivalent if implemented.

#### Scenario: Help command is visible

- **GIVEN** the TUI is mounted
- **WHEN** the footer or hint strip is rendered
- **THEN** it SHALL mention `/help` or equivalent.

---

### Requirement: History and status changes shall be observable

TUI history navigation and operational status changes SHALL be logged through best-effort observability.

#### Scenario: History push is logged

- **GIVEN** the user submits a non-empty input
- **WHEN** the input is added to history
- **THEN** a `TUI_HISTORY_PUSHED` or equivalent event SHALL be emitted.

#### Scenario: History navigation is logged without raw sensitive content

- **GIVEN** the user presses Up or Down
- **WHEN** history navigation occurs
- **THEN** a history navigation event SHALL be emitted
- **AND** the event SHOULD avoid raw full input unless redaction is applied.

#### Scenario: Status transition is logged

- **GIVEN** the runtime status changes from one state to another
- **WHEN** the transition occurs
- **THEN** a `TUI_STATUS_CHANGED` or equivalent event SHALL be emitted.

---

### Requirement: Persistent history shall be safe if implemented

If persistent input history is implemented, it SHALL be bounded and redaction-aware.

#### Scenario: Persistent history can be disabled

- **GIVEN** persistent history is implemented
- **WHEN** the user disables it via config/env
- **THEN** new inputs SHALL NOT be written to persistent history.

#### Scenario: Sensitive-looking values are not persisted raw

- **GIVEN** input contains sensitive-looking tokens or secrets
- **WHEN** persistent history is enabled
- **THEN** raw sensitive values SHALL be skipped or redacted before storage.

#### Scenario: Persistent history is bounded

- **GIVEN** more than the configured maximum history entries exist
- **WHEN** history is loaded or saved
- **THEN** only the latest bounded set SHALL be retained.

---

### Requirement: Tests and validation shall prove completion

The implementation SHALL include tests and validation evidence for history, UI states, layout constraints, and docs.

#### Scenario: History tests pass

- **GIVEN** the implementation is complete
- **WHEN** tests run
- **THEN** they SHALL prove Up/Down history behavior, draft restore, dedupe, and empty-input skip.

#### Scenario: Status tests pass

- **GIVEN** the implementation is complete
- **WHEN** tests run
- **THEN** they SHALL prove command, chat, tool, data, warning, and error state transitions.

#### Scenario: Layout regression tests pass

- **GIVEN** the implementation is complete
- **WHEN** tests run
- **THEN** they SHALL prove the default layout remains one output stream and one composer input.

#### Scenario: Documentation is updated

- **GIVEN** the implementation is complete
- **WHEN** docs are inspected
- **THEN** TUI docs SHALL explain input history, keybindings, status states, and troubleshooting.

