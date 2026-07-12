# Specification: Opencode-like TUI workspace

## Purpose

Provide a minimal opencode-like research workspace with deterministic routing between chat input and slash commands.
## Requirements
### Requirement: Default TUI shall use a two-region opencode-like layout

The default `vnalpha tui` interface SHALL expose exactly two primary visible regions: one output stream and one composer input.

#### Scenario: App mounts two primary regions

- **GIVEN** the user launches `vnalpha tui`
- **WHEN** the TUI is composed
- **THEN** the default layout SHALL include `OutputStream(id="output-stream")`
- **AND** SHALL include `ComposerInput(id="composer-input")`.

#### Scenario: Default layout has no main workspace switcher

- **GIVEN** the default TUI is mounted
- **WHEN** the DOM is inspected
- **THEN** no `ContentSwitcher(id="main-workspace")` SHALL be mounted.

#### Scenario: Default layout has no secondary chat panel

- **GIVEN** the default TUI is mounted
- **WHEN** the DOM is inspected
- **THEN** no `ChatPanel(id="chat-panel")` SHALL be mounted as a separate secondary panel.

#### Scenario: Default layout has one input

- **GIVEN** the default TUI is mounted
- **WHEN** Textual `Input` widgets are counted
- **THEN** exactly one input widget SHALL exist.

---

### Requirement: ComposerInput shall be the only user input surface

The composer SHALL accept natural-language questions and slash commands through the same input field,
and when the current input starts with `/`, the composer SHALL provide deterministic slash-command
discovery that updates while typing.

#### Scenario: User submits text

- **WHEN** the composer contains non-empty text
- **THEN** pressing Enter SHALL emit a submitted message containing the text
- **AND** SHALL clear the input
- **AND** SHALL route through the existing composer submission flow.

#### Scenario: Empty submission is ignored

- **WHEN** the composer contains only whitespace
- **AND** Enter is pressed
- **THEN** no route action SHALL run.

#### Scenario: Clear input behavior works

- **WHEN** the composer contains text
- **AND** Esc is pressed
- **THEN** the composer input SHALL be cleared.

#### Scenario: Slash mode opens suggestions

- **WHEN** the user types `/` as the first non-empty character
- **THEN** the composer SHALL display an available-command suggestion list.

#### Scenario: Slash mode filters suggestions while typing

- **WHEN** the user continues typing after `/`
- **THEN** the suggestion list SHALL only include command names with a case-insensitive prefix match
  against the typed text (after `/`).

#### Scenario: Suggestion list is hidden outside slash mode

- **WHEN** the composer input does not start with `/`
- **THEN** the slash-command suggestion list SHALL be hidden.

#### Scenario: Command route remains unchanged on Enter

- **WHEN** the user submits a command such as `/scan` from composer
- **THEN** routing SHALL continue to execute through the existing slash-command execution path.

### Requirement: OutputStream shall render all results inline

The output stream SHALL be the single visible destination for assistant output, command results, tool trace, errors, warnings, logs summaries, repair output, and deploy output.

#### Scenario: User input is displayed

- **GIVEN** the user submits text
- **WHEN** the input is routed
- **THEN** OutputStream SHALL append the user input.

#### Scenario: Command result is displayed

- **GIVEN** a slash command returns a command result
- **WHEN** the result is rendered
- **THEN** OutputStream SHALL append the command and result markup.

#### Scenario: Assistant answer is displayed

- **GIVEN** ChatController emits an assistant message
- **WHEN** the callback runs
- **THEN** OutputStream SHALL append the assistant message.

#### Scenario: Tool trace is displayed

- **GIVEN** a tool trace event occurs
- **WHEN** the trace callback runs
- **THEN** OutputStream SHALL append the trace status inline.

#### Scenario: Error is displayed

- **GIVEN** routing or rendering fails
- **WHEN** the error is handled
- **THEN** OutputStream SHALL append an error block
- **AND** the error SHALL be captured by observability.

---

### Requirement: Input router shall route plain language to ChatController

Plain-language input SHALL use the existing ChatController orchestration path.

#### Scenario: Plain language input routes to chat

- **GIVEN** the user submits `scan VN30 today`
- **WHEN** the input does not begin with `/`
- **THEN** the router SHALL call `ChatController.handle_turn()` or equivalent.

#### Scenario: Chat callbacks render to OutputStream

- **GIVEN** ChatController emits message callbacks
- **WHEN** callbacks are received
- **THEN** they SHALL render into OutputStream rather than a secondary chat panel.

#### Scenario: Chat trace renders to OutputStream

- **GIVEN** ChatController emits tool trace callbacks
- **WHEN** callbacks are received
- **THEN** they SHALL render into OutputStream.

---

### Requirement: Input router shall route slash commands to CommandExecutor

Slash commands SHALL run through the existing command execution layer.

#### Scenario: Slash command routes to CommandExecutor

- **GIVEN** the user submits `/scan`
- **WHEN** the input begins with `/`
- **THEN** the router SHALL call `CommandExecutor.execute()` or equivalent.

#### Scenario: Command result uses existing renderer

- **GIVEN** CommandExecutor returns a result
- **WHEN** the result is displayed
- **THEN** the TUI SHALL use an existing command result renderer where feasible
- **AND** SHALL append the result to OutputStream.

#### Scenario: Command failure renders inline

- **GIVEN** CommandExecutor fails or returns a non-success status
- **WHEN** the result is displayed
- **THEN** OutputStream SHALL render an error or failure block.

---

### Requirement: Logs, repair, and deploy workflows shall be accessible from the composer

The opencode-like TUI SHALL allow operational workflows from the same input box.

#### Scenario: Logs command is supported

- **GIVEN** the user submits `/logs errors --latest`
- **WHEN** the command is routed
- **THEN** OutputStream SHALL display the logs result or a clear unsupported-command message.

#### Scenario: Repair command is supported

- **GIVEN** the user submits `/repair prepare --latest`
- **WHEN** the command is routed
- **THEN** OutputStream SHALL display repair bundle information or a clear unsupported-command message.

#### Scenario: Deploy command is supported

- **GIVEN** the user submits `/deploy verify candidate-x`
- **WHEN** the command is routed
- **THEN** OutputStream SHALL display deploy verification information or a clear unsupported-command message.

---

### Requirement: Plan approval and cancellation shall work from the composer

Pending plan actions SHALL not require a separate panel or screen.

#### Scenario: Approve pending plan

- **GIVEN** ChatController has a pending plan
- **WHEN** the user submits `/approve` or `approve`
- **THEN** the router SHALL approve the pending plan
- **AND** OutputStream SHALL show the result.

#### Scenario: Cancel pending plan

- **GIVEN** ChatController has a pending plan
- **WHEN** the user submits `/cancel` or `cancel`
- **THEN** the router SHALL cancel the pending plan
- **AND** OutputStream SHALL show the result.

---

### Requirement: Visible output clearing shall not delete audit history

Clearing the visible output stream SHALL not delete persisted logs or audit history.

#### Scenario: Clear visible stream

- **GIVEN** OutputStream contains visible content
- **WHEN** the user submits `/clear` or presses the clear binding
- **THEN** the visible OutputStream SHALL be cleared
- **AND** audit logs SHALL remain intact.

---

### Requirement: Closed-loop observability shall be preserved for TUI interactions

The TUI refactor SHALL preserve file-based observability and closed-loop logging behavior.

#### Scenario: TUI input event is logged

- **GIVEN** the user submits non-empty input
- **WHEN** routing begins
- **THEN** a `TUI_INPUT_SUBMITTED` or equivalent event SHALL be written.

#### Scenario: Slash command lifecycle is logged

- **GIVEN** the user submits a slash command
- **WHEN** the command runs
- **THEN** command lifecycle events SHALL be written with a non-empty correlation ID.

#### Scenario: Natural-language route is logged

- **GIVEN** the user submits plain-language input
- **WHEN** the input routes to chat
- **THEN** chat lifecycle events SHALL be written with a non-empty correlation ID.

#### Scenario: Render failure is logged

- **GIVEN** OutputStream rendering raises an exception
- **WHEN** the exception is handled
- **THEN** an observability error event SHALL be written.

---

### Requirement: Legacy dashboard screens shall not be default workflow

Legacy screens may remain importable but SHALL NOT be mounted in the default TUI path.

#### Scenario: Default DOM excludes legacy screens

- **GIVEN** the default TUI is mounted
- **WHEN** the DOM is inspected
- **THEN** `HomeScreen`, `WatchlistScreen`, `CommandScreen`, `AssistantScreen`, `RejectedScreen`, `QualityScreen`, `OutcomeScreen`, and `LogScreen` SHALL NOT be mounted as default primary screens.

#### Scenario: Legacy modules remain safe

- **GIVEN** legacy screen modules remain in the repository
- **WHEN** tests import them
- **THEN** imports SHALL not fail unless removal is explicitly documented.

---

### Requirement: Tests shall prove the new interaction model

The implementation SHALL include tests for layout, routing, rendering, and observability.

#### Scenario: Layout tests pass

- **GIVEN** the default app is mounted headlessly
- **WHEN** tests inspect the DOM
- **THEN** they SHALL prove one OutputStream, one ComposerInput, one Input, no ContentSwitcher, and no secondary ChatPanel.

#### Scenario: Routing tests pass

- **GIVEN** plain-language and slash-command inputs are submitted
- **WHEN** tests run
- **THEN** plain-language routes to ChatController and slash commands route to CommandExecutor.

#### Scenario: Rendering tests pass

- **GIVEN** command, chat, trace, and error outputs occur
- **WHEN** tests inspect OutputStream behavior
- **THEN** all are rendered inline.

#### Scenario: Observability tests pass

- **GIVEN** TUI input is submitted
- **WHEN** routing occurs
- **THEN** observability events SHALL be written or mocked as expected.

