# Specification: OpenCode-style Research Chat Workspace

## ADDED Requirements

### Requirement: TUI shall provide a persistent split-pane chat workspace

The TUI SHALL render a persistent chat panel alongside the main research workspace.

The chat panel SHALL remain visible when the user switches between watchlist, detail, quality, outcome, command, and assistant views unless explicitly hidden.

#### Scenario: Chat panel remains visible across screen changes

- **GIVEN** the TUI is open on the watchlist view
- **AND** the chat panel is visible
- **WHEN** the user switches to the detail view
- **THEN** the chat panel SHALL remain mounted and visible
- **AND** the existing chat transcript SHALL remain visible.

#### Scenario: Chat panel can be toggled and focused

- **GIVEN** the TUI is open
- **WHEN** the user presses the toggle-chat binding
- **THEN** the chat panel visibility SHALL toggle
- **WHEN** the user presses the focus-chat binding
- **THEN** focus SHALL move to the chat input.

---

### Requirement: ChatPanel shall route slash commands through CommandExecutor

All research slash commands entered into ChatPanel SHALL be executed through `CommandExecutor`.

ChatPanel SHALL NOT maintain an independent command parser/executor path for research slash commands.

#### Scenario: Slash command uses shared execution path

- **GIVEN** the user enters `/scan` in the chat input
- **WHEN** ChatPanel executes the command
- **THEN** execution SHALL call `CommandExecutor(surface='tui-chat')`
- **AND** the command SHALL create a `research_session`
- **AND** local tool calls SHALL create `tool_trace` rows.

#### Scenario: Chat slash command uses target date

- **GIVEN** the chat workspace target date is `2026-07-06`
- **WHEN** the user enters `/scan` without an explicit date
- **THEN** CommandExecutor SHALL receive default date `2026-07-06`
- **AND** results SHALL be scoped to that date.

---

### Requirement: ChatPanel shall not depend on a long-lived shared DuckDB connection

Chat execution SHALL use a connection factory or short-lived DuckDB connections per turn.

Each turn SHALL run migrations before execution.

#### Scenario: Slash command works without pre-injected connection

- **GIVEN** ChatPanel is constructed without a direct DuckDB connection
- **WHEN** the user enters `/quality FPT`
- **THEN** ChatController SHALL open a connection
- **AND** run migrations
- **AND** execute the command successfully if data exists.

---

### Requirement: Chat transcript shall be persisted

The system SHALL persist chat sessions and ordered chat messages.

Required tables:

```text
chat_session
chat_message
```

Required message roles:

```text
user
assistant
system
tool
trace
plan
error
```

Required message types:

```text
plain_text
slash_command
assistant_answer
plan_preview
tool_trace_event
command_result
validation_error
refusal
error
```

#### Scenario: User and assistant messages are persisted

- **GIVEN** a user asks `Show strongest candidates`
- **WHEN** the assistant answers
- **THEN** a `chat_session` SHALL exist
- **AND** the user prompt SHALL be persisted as a `chat_message`
- **AND** the assistant answer SHALL be persisted as a later `chat_message` in the same session.

#### Scenario: Command result is linked to research session

- **GIVEN** the user enters `/scan`
- **WHEN** the command completes
- **THEN** a chat message of type `command_result` SHALL be persisted
- **AND** it SHALL include or link to the `research_session_id` created by CommandExecutor.

---

### Requirement: Chat turns shall link to assistant sessions and tool traces

Assistant chat turns SHALL link to the `assistant_session` and relevant `tool_trace` records.

#### Scenario: Assistant answer links to assistant session

- **GIVEN** a user asks `Explain FPT`
- **WHEN** the assistant completes
- **THEN** the assistant answer chat message SHALL include `assistant_session_id`
- **AND** the assistant session SHALL include plan and answer metadata.

#### Scenario: Trace events link to tool traces

- **GIVEN** an assistant plan calls `candidate.explain` and `quality.get_status`
- **WHEN** the tools execute
- **THEN** trace events SHALL be visible in the chat log
- **AND** persisted trace messages SHALL include `tool_trace_id` or `tool_trace_ids_json`.

---

### Requirement: Chat shall support multi-turn context

The chat workspace SHALL maintain deterministic context for follow-up prompts.

At minimum, context SHALL include:

```text
chat_session_id
target_date
last_symbols
selected_symbol
selected_rank
last_watchlist_date
last_command
last_plan
last_tool_outputs_summary
```

#### Scenario: Follow-up resolves top candidate

- **GIVEN** the user previously ran `/scan` and FPT was rank 1
- **WHEN** the user asks `explain the first one`
- **THEN** the assistant SHALL resolve `the first one` to FPT
- **AND** the plan SHALL use FPT explicitly.

#### Scenario: Context does not invent symbols

- **GIVEN** there is no selected symbol and no previous symbol context
- **WHEN** the user asks `explain that one`
- **THEN** the assistant SHALL ask for clarification or return a validation message
- **AND** it SHALL NOT invent a symbol.

---

### Requirement: Chat shall support plan preview and approval

The chat workspace SHALL support plan preview before assistant tool execution.

Supported execution modes:

```text
AUTO_EXECUTE_SAFE_READ_ONLY
PLAN_THEN_APPROVE
PLAN_ONLY
```

#### Scenario: Plan preview is persisted

- **GIVEN** chat mode is `PLAN_THEN_APPROVE`
- **WHEN** the user asks `Compare FPT and VNM`
- **THEN** the assistant SHALL build a plan
- **AND** render the plan in the chat log
- **AND** persist a `plan_preview` chat message
- **AND** wait for approval before executing tools.

#### Scenario: Approved plan executes tools

- **GIVEN** a pending plan is visible
- **WHEN** the user approves it
- **THEN** the assistant SHALL execute the planned tools
- **AND** tool traces SHALL be persisted and rendered.

#### Scenario: Canceled plan does not execute tools

- **GIVEN** a pending plan is visible
- **WHEN** the user cancels it
- **THEN** no planned tool calls SHALL execute
- **AND** a cancellation message SHALL be persisted.

---

### Requirement: Chat shall provide streaming or staged response events

The chat workspace SHALL provide live progress feedback while assistant work is running.

If true token streaming is available, the chat SHALL render streamed answer tokens.

If true token streaming is not available, the chat SHALL render staged events:

```text
classifying
planning
tool running
tool success/failure
synthesizing
final answer
```

#### Scenario: Staged fallback shows progress before final answer

- **GIVEN** token streaming is unavailable
- **WHEN** the assistant handles a prompt that calls tools
- **THEN** the chat SHALL show classification/planning/tool events before the final answer
- **AND** the final answer SHALL still be persisted.

---

### Requirement: Tool trace timeline shall be visible and replayable

The chat workspace SHALL render tool trace events and allow users to inspect recent traces.

#### Scenario: Trace command shows previous turn traces

- **GIVEN** the previous assistant turn executed two tools
- **WHEN** the user enters `/trace`
- **THEN** the chat SHALL show those tool names, statuses, durations, and trace IDs.

---

### Requirement: Chat-local commands shall be supported

The chat workspace SHALL support chat-local commands distinct from research slash commands.

Required chat-local commands:

```text
/new
/clear
/context
/plan
/trace
/help
```

#### Scenario: New chat starts a new session

- **GIVEN** the current chat session contains messages
- **WHEN** the user enters `/new`
- **THEN** a new `chat_session` SHALL be created
- **AND** subsequent messages SHALL belong to the new session.

#### Scenario: Clear preserves transcript by default

- **GIVEN** the chat log contains visible messages
- **WHEN** the user enters `/clear`
- **THEN** the visible log SHALL be cleared
- **AND** the persisted transcript SHALL remain available unless explicit deletion is requested and implemented.

#### Scenario: Context command shows current context

- **GIVEN** the user has run `/scan` and selected FPT
- **WHEN** the user enters `/context`
- **THEN** the chat SHALL show target date, selected symbol, last symbols, and last command summary.

---

### Requirement: Chat shall enforce research-only tool policy

The chat workspace SHALL only allow research-safe tools.

It SHALL NOT expose broker, order, allocation, account, margin, payment, or portfolio-mutating tools.

#### Scenario: Disallowed tool is refused

- **GIVEN** an assistant plan attempts to call `broker.place_order`
- **WHEN** plan validation runs
- **THEN** the request SHALL be refused or validation-failed
- **AND** no broker/order tool SHALL execute.

---

### Requirement: Chat shall handle validation, refusal, and runtime errors clearly

The chat workspace SHALL render validation errors, refusals, and runtime errors differently.

```text
validation error -> yellow non-fatal message
refusal          -> policy/refusal message
runtime failure  -> red error message
```

#### Scenario: Invalid slash command is validation error

- **GIVEN** the user enters an invalid research slash command
- **WHEN** validation fails
- **THEN** the chat SHALL render a validation message
- **AND** persist a `validation_error` chat message.

#### Scenario: Tool failure is rendered and traced

- **GIVEN** a tool call fails at runtime
- **WHEN** the failure occurs
- **THEN** the tool trace SHALL be marked `FAILED`
- **AND** the chat SHALL render an error message linked to that trace.

---

### Requirement: Chat workspace shall be covered by targeted tests

The implementation SHALL include tests for layout, controller, persistence, command routing, assistant context, plan approval, trace rendering, and safety.

Required test coverage:

```text
split-pane shell
chat panel persistence across screen changes
slash command routing through CommandExecutor
short-lived DB connection per turn
chat_session/chat_message persistence
multi-turn context resolution
plan preview/approve/cancel
staged response fallback or token streaming
trace event render and replay
chat-local commands
research-only allowlist
validation/refusal/runtime error rendering
```

#### Scenario: Full targeted suite passes

- **GIVEN** Phase 5.10 is implemented
- **WHEN** `cd vnalpha && pytest -q` runs
- **THEN** all Phase 5.10 chat workspace tests SHALL pass
- **AND** existing Phase 5.8 and Phase 5.9 tests SHALL continue to pass.
