# tui-control-plane Specification Delta

## ADDED Requirements

### Requirement: Production TUI router shall use real CommandExecutor setup

The default TUI router SHALL initialize slash command execution using a live warehouse connection and the production `CommandExecutor` constructor.

#### Scenario: Router creates a command executor

- **WHEN** `TuiInputRouter` starts
- **THEN** it opens a DuckDB connection
- **AND** runs migrations on that connection
- **AND** constructs `CommandExecutor(conn, surface="tui", default_date=target_date)`
- **AND** keeps the connection available for command execution

#### Scenario: Router shuts down

- **WHEN** the TUI app shuts down
- **THEN** the router closes any owned command connection exactly once

### Requirement: Composer shall bridge operational commands

The default composer path SHALL route `/logs`, `/repair`, and `/deploy` before generic research slash command dispatch.

#### Scenario: Latest errors are requested

- **WHEN** the user submits `/logs errors --latest`
- **THEN** the TUI routes the request through the logs bridge
- **AND** renders the result inline in `OutputStream`
- **AND** emits command lifecycle observability

#### Scenario: Latest run is summarized

- **WHEN** the user submits `/logs summarize --latest`
- **THEN** the TUI routes the request through the logs bridge
- **AND** renders the summary inline

#### Scenario: Repair bundle is prepared

- **WHEN** the user submits `/repair prepare --latest`
- **THEN** the TUI routes the request through the repair bridge
- **AND** renders the repair bundle path or status inline

#### Scenario: Repair status is requested

- **WHEN** the user submits `/repair status <repair-id>`
- **THEN** the TUI routes the request through the repair bridge
- **AND** renders repair status inline

#### Scenario: Research artifact deployment candidate is verified

- **WHEN** the user submits `/deploy verify <candidate>`
- **THEN** the TUI routes the request through the deploy bridge
- **AND** treats deploy as research artifact verification only
- **AND** does not touch broker, order, account, portfolio, margin, transfer, allocation, or trading execution systems

### Requirement: TUI command lifecycle shall be observable

Every non-empty TUI command submission SHALL emit lifecycle events with a non-empty correlation ID.

#### Scenario: Command succeeds

- **WHEN** a slash command succeeds
- **THEN** the system emits `TUI_INPUT_SUBMITTED`
- **AND** emits `TUI_COMMAND_ROUTED`
- **AND** emits `COMMAND_STARTED`
- **AND** emits `COMMAND_SUCCEEDED`
- **AND** persists redacted command evidence

#### Scenario: Command fails

- **WHEN** a slash command fails
- **THEN** the system emits `COMMAND_FAILED`
- **AND** captures the exception
- **AND** renders the error inline
- **AND** preserves redaction-by-default

### Requirement: TUI rendering shall be thread-safe

Callbacks invoked from worker threads SHALL NOT mutate Textual widgets directly.

#### Scenario: Assistant callback renders from worker path

- **WHEN** `ChatController.handle_turn()` runs in a worker thread
- **AND** it invokes an assistant message callback
- **THEN** the callback marshals rendering onto the Textual app loop or message queue
- **AND** no direct worker-thread widget mutation occurs

### Requirement: Default TUI DOM shall remain opencode-like

The production control-plane change SHALL preserve the single output stream and single composer input default model.

#### Scenario: App mounts

- **WHEN** `vnalpha tui` starts
- **THEN** exactly one `OutputStream` is mounted
- **AND** exactly one `ComposerInput` is mounted
- **AND** exactly one Textual `Input` exists in the default DOM
- **AND** no `ContentSwitcher` is mounted in the default path
- **AND** no persistent secondary `ChatPanel` is mounted in the default path

### Requirement: read-only research boundary shall be preserved

The production control plane SHALL NOT introduce any trading execution capability.

#### Scenario: Disallowed trading-like command or tool is requested

- **WHEN** a user request implies broker, order, account, portfolio, margin, transfer, allocation, or trading execution behavior
- **THEN** the system refuses or reports unsupported behavior
- **AND** logs the refusal
- **AND** does not create, route, or execute a trading action
