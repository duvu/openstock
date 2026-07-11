# Spec: TUI Assistant Safe Execution

## Purpose

TBD - created while archiving change safe-tools-auto-execute-policy to establish the baseline required by its modified requirements.
## Requirements
### Requirement: Auto mode semantics

Auto mode SHALL mean "auto-execute all tools in `SAFE_TOOLS`", not "auto-execute read-only tools only".

#### Scenario: safe internal write tool

- **GIVEN** auto mode is active
- **AND** a plan contains `note.create` or `data.fetch`
- **WHEN** the tool is listed in `SAFE_TOOLS`
- **THEN** the plan SHALL execute automatically.

### Requirement: Documentation accuracy

Docs and OpenSpec task checkboxes SHALL only claim behavior that is implemented or explicitly marked unsupported/preview.

#### Scenario: smoke flag claim

- **GIVEN** docs or tests mention `vnalpha tui --smoke`
- **WHEN** the CLI does not implement `--smoke`
- **THEN** the claim SHALL be removed or the flag SHALL be implemented with a meaningful test.

### Requirement: Single SAFE_TOOLS policy source

The system SHALL define one canonical `SAFE_TOOLS` source of truth for assistant and TUI auto-executable tools.

#### Scenario: planner validates against SAFE_TOOLS

- **GIVEN** a plan step with tool name `candidate.explain`
- **WHEN** the planner validates the plan
- **THEN** the planner SHALL check the tool through the canonical `SAFE_TOOLS` policy
- **AND** the planner SHALL NOT use a separate planner-local allowlist.

#### Scenario: executor validates against SAFE_TOOLS

- **GIVEN** a plan step with tool name `data.fetch`
- **WHEN** the executor is about to run the step
- **THEN** the executor SHALL check the tool through the canonical `SAFE_TOOLS` policy
- **AND** the executor SHALL execute the step automatically if the tool is safe.

#### Scenario: unknown tool is refused

- **GIVEN** a plan step with tool name `unknown.tool`
- **WHEN** the planner or executor validates the step
- **THEN** the system SHALL refuse the tool
- **AND** the system SHALL render/log a clear unsafe-tool error.

### Requirement: Trusted safe tools auto-execute

The system SHALL automatically execute every tool listed in `SAFE_TOOLS` during normal assistant/TUI auto mode.

#### Scenario: read research tool auto-executes

- **GIVEN** a plan containing `candidate.explain`
- **AND** `candidate.explain` is listed in `SAFE_TOOLS`
- **WHEN** the assistant is in auto mode
- **THEN** the assistant SHALL execute the plan automatically.

#### Scenario: internal note write auto-executes

- **GIVEN** a plan containing `note.create`
- **AND** `note.create` is listed in `SAFE_TOOLS`
- **WHEN** the assistant is in auto mode
- **THEN** the assistant SHALL execute the plan automatically
- **AND** the assistant SHALL NOT require approval solely because the tool writes an internal research note.

#### Scenario: internal data provisioning auto-executes

- **GIVEN** a plan containing `data.fetch`
- **AND** `data.fetch` is listed in `SAFE_TOOLS`
- **WHEN** the assistant is in auto mode
- **THEN** the assistant SHALL execute the plan automatically
- **AND** the assistant SHALL NOT require approval solely because the tool writes local warehouse data.

### Requirement: Trading execution boundary is hard-denied

The system SHALL permanently deny broker/order/account/portfolio/margin/trading execution tools.

#### Scenario: broker tool is denied

- **GIVEN** a future tool named `broker.connect`
- **WHEN** planner, executor, or chat safety validates the tool
- **THEN** the system SHALL deny it
- **AND** the tool SHALL NOT execute even if referenced by a prompt or plan.

#### Scenario: order tool is denied

- **GIVEN** a future tool named `order.place`
- **WHEN** planner, executor, or chat safety validates the tool
- **THEN** the system SHALL deny it
- **AND** the tool SHALL NOT execute.

#### Scenario: account tool is denied

- **GIVEN** a future tool named `account.get_balance`
- **WHEN** planner, executor, or chat safety validates the tool
- **THEN** the system SHALL deny it
- **AND** the tool SHALL NOT execute.

#### Scenario: portfolio tool is denied

- **GIVEN** a future tool named `portfolio.rebalance`
- **WHEN** planner, executor, or chat safety validates the tool
- **THEN** the system SHALL deny it
- **AND** the tool SHALL NOT execute.

### Requirement: TUI operational command bridge

The TUI SHALL route `/logs`, `/repair`, and `/deploy` commands through an explicit operational command bridge before generic research slash command routing.

#### Scenario: logs command is routed operationally

- **GIVEN** the user submits `/logs errors --latest`
- **WHEN** `TuiInputRouter` routes the input
- **THEN** it SHALL route the command to the operational bridge
- **AND** it SHALL NOT route the command to the research `CommandExecutor` registry.

#### Scenario: repair command is routed operationally

- **GIVEN** the user submits `/repair prepare --latest`
- **WHEN** `TuiInputRouter` routes the input
- **THEN** it SHALL route the command to the operational bridge
- **AND** it SHALL NOT route the command to the research `CommandExecutor` registry.

#### Scenario: deploy command is routed operationally

- **GIVEN** the user submits `/deploy verify candidate-123`
- **WHEN** `TuiInputRouter` routes the input
- **THEN** it SHALL route the command to the operational bridge
- **AND** it SHALL NOT route the command to the research `CommandExecutor` registry.

#### Scenario: unsupported operational subcommand

- **GIVEN** the user submits an unsupported operational subcommand
- **WHEN** the operational bridge receives it
- **THEN** the TUI SHALL render a clear inline unsupported message
- **AND** it SHALL preserve command lifecycle logging.

### Requirement: TUI command lifecycle logging

Every TUI slash or operational command SHALL emit command lifecycle observability events.

#### Scenario: command succeeds

- **GIVEN** the user submits `/help`
- **WHEN** the TUI executes the command successfully
- **THEN** `commands.jsonl` SHALL include `COMMAND_STARTED`
- **AND** `commands.jsonl` SHALL include `COMMAND_SUCCEEDED`
- **AND** the correlation ID SHALL be non-empty and not `unset`.

#### Scenario: command fails

- **GIVEN** the user submits a command that raises an exception
- **WHEN** the TUI handles the failure
- **THEN** `commands.jsonl` SHALL include `COMMAND_STARTED`
- **AND** `commands.jsonl` SHALL include `COMMAND_FAILED`
- **AND** the exception SHALL be captured through `capture_exception()`
- **AND** the user SHALL see an inline error.

### Requirement: TUI command connection lifecycle

The TUI router SHALL explicitly close any DuckDB command connection it owns.

#### Scenario: app unmounts

- **GIVEN** `TuiInputRouter` opened a DuckDB connection for `CommandExecutor`
- **WHEN** `VnAlphaApp` unmounts
- **THEN** the app SHALL call `router.close()`
- **AND** the router SHALL close the command connection exactly once.

### Requirement: Textual-safe worker callback dispatch

TUI callbacks invoked from worker threads SHALL marshal UI updates back onto the Textual app loop.

#### Scenario: assistant message from worker thread

- **GIVEN** `ChatController.handle_turn()` is running in `asyncio.to_thread()`
- **WHEN** the assistant emits a message callback
- **THEN** the callback SHALL NOT update Textual widgets directly from the worker thread
- **AND** the message SHALL render through a Textual-safe dispatcher or message queue.

#### Scenario: trace event from worker thread

- **GIVEN** a tool trace event is emitted from a worker thread
- **WHEN** the TUI receives the trace callback
- **THEN** the trace rendering SHALL be marshalled onto the Textual app loop.

