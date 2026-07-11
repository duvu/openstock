# tui-control-plane Specification Delta

## ADDED Requirements

### Requirement: Production TUI router shall own a real command executor safely

The default `vnalpha` TUI router SHALL create and own the production command
executor and its DuckDB connection without leaking or closing it while a route
is using it.

#### Scenario: Router creates a command executor

- **WHEN** `TuiInputRouter` starts
- **THEN** it opens a DuckDB connection through `get_connection()`
- **AND** runs `run_migrations(conn=conn)` before use
- **AND** constructs `CommandExecutor(conn, surface="tui", default_date=target_date)`
- **AND** retains that exact connection only for router command execution.

#### Scenario: Command setup fails

- **WHEN** opening the connection, running migrations, or constructing the
  executor fails
- **THEN** the router closes any partially opened connection exactly once
- **AND** captures the exception with redaction-by-default
- **AND** records `TUI_COMMAND_SETUP_FAILED`
- **AND** slash commands render an actionable degraded-mode message rather than
  only `CommandExecutor unavailable.`
- **AND** chat remains available if its own setup succeeded.

#### Scenario: Router shuts down during active work

- **WHEN** the TUI app unmounts while a route is active
- **THEN** the router stops accepting new submissions
- **AND** defers command-connection close until the active route exits
- **AND** closes the owned connection exactly once
- **AND** no route uses a closed connection.

### Requirement: TUI shall serialize submitted work

The router SHALL allow at most one active chat, research-command, or
operational-command route at a time.

#### Scenario: Submission arrives while a route is active

- **WHEN** a non-empty submission arrives while another route is active
- **THEN** the router creates a fresh correlation ID for the new submission
- **AND** emits `TUI_INPUT_SUBMITTED` followed by `TUI_INPUT_REJECTED`
- **AND** renders a redacted inline busy warning
- **AND** does not call `CommandExecutor`, `ChatController`, or an operational
  domain action for the rejected submission.

#### Scenario: Control input arrives while a route is active

- **WHEN** `/approve`, `/cancel`, or `/clear` is submitted while a route is active
- **THEN** it follows the same rejection policy
- **AND** it does not mutate `ChatController` or visible widgets concurrently.

#### Scenario: Router is closing

- **WHEN** a non-empty submission arrives after shutdown has started
- **THEN** the router emits `TUI_INPUT_REJECTED`
- **AND** it does not start work or reacquire a connection.

### Requirement: Composer shall bridge only documented operational commands

The default composer path SHALL route `/logs`, `/repair`, and `/deploy` before
generic research slash-command dispatch, using a strict fixed grammar.

#### Scenario: Documented operational form is submitted

- **WHEN** the user submits one of these forms:
  - `/logs errors --latest`
  - `/logs summarize --latest`
  - `/repair prepare --latest`
  - `/repair status <repair-id>`
  - `/deploy verify <candidate>`
  - `/deploy promote <candidate> --deployment-id <id>`
  - `/deploy rollback <deployment-id>`
- **THEN** the TUI routes it through the operational bridge
- **AND** it does not route it through the research `CommandExecutor`
- **AND** it renders the redacted domain result inline in `OutputStream`.

#### Scenario: Latest run is resolved

- **WHEN** an accepted operational form includes `--latest`
- **THEN** the bridge resolves the latest-run pointer once at operational
  execution start
- **AND** uses that resolved run for the whole action
- **AND** does not accept a user-supplied filesystem path in place of `--latest`.

#### Scenario: Identifier is invalid or grammar is unsupported

- **WHEN** a repair ID, candidate, deployment ID, option ordering, or command
  form is invalid
- **THEN** the bridge invokes no domain action
- **AND** the TUI renders a clear redacted unsupported/invalid message inline
- **AND** it records the failure lifecycle.

#### Scenario: Deploy domain gate blocks an operation

- **WHEN** a delegated deploy verify, promote, or rollback operation is blocked
  by its domain validation or promotion gate
- **THEN** the TUI renders the redacted block reason inline
- **AND** emits `COMMAND_FAILED`
- **AND** does not bypass, override, or redefine the Phase D gate.

### Requirement: TUI submission lifecycle shall be correlated and truthful

Every non-empty TUI submission SHALL receive a fresh, non-empty correlation ID
before any route, rendering, or worker-dispatch action.

#### Scenario: Research command succeeds

- **WHEN** a slash command returns `SUCCESS`, `EMPTY_RESULT`, or `PARTIAL`
- **THEN** the system emits, with the same correlation ID,
  `TUI_INPUT_SUBMITTED`, `TUI_COMMAND_ROUTED`, `COMMAND_STARTED`, and
  `COMMAND_SUCCEEDED`
- **AND** persists redacted command evidence.

#### Scenario: Command returns a terminal failure result

- **WHEN** a command returns `FAILED` or `VALIDATION_ERROR` without raising
- **THEN** the system emits `COMMAND_FAILED`, not `COMMAND_SUCCEEDED`
- **AND** records the returned status and redacted failure details
- **AND** renders the result inline.

#### Scenario: Command or operational action raises

- **WHEN** execution raises an exception
- **THEN** the system emits `COMMAND_FAILED` with the submission correlation ID
- **AND** captures the exception with `capture_exception()`
- **AND** renders a redacted inline error.

#### Scenario: Chat or control input is routed

- **WHEN** a natural-language or accepted local control input is submitted
- **THEN** the system emits `TUI_INPUT_SUBMITTED` and the corresponding
  `TUI_CHAT_ROUTED` or `TUI_CONTROL_ROUTED` event with the same correlation ID
- **AND** it does not emit command lifecycle events unless a command actually
  starts.

#### Scenario: Rendering fails

- **WHEN** a TUI rendering operation fails
- **THEN** the system persists `TUI_RENDER_ERROR` with the active correlation ID
- **AND** captures the exception without writing unredacted input or secrets.

### Requirement: TUI rendering shall be safe across worker and app lifetimes

Callbacks invoked from worker threads SHALL NOT mutate Textual widgets directly.

#### Scenario: Worker callback reaches a mounted app

- **WHEN** a `ChatController` assistant-message, trace, warning, or error
  callback is invoked from a worker thread while the app is mounted
- **THEN** it marshals rendering through the app's Textual-safe dispatcher or
  message queue
- **AND** output and status widgets are updated only on the Textual app loop.

#### Scenario: Dispatcher is absent or app has unmounted

- **WHEN** such a callback occurs without a live dispatcher or after unmount
- **THEN** the callback does not mutate a widget directly
- **AND** it is safely dropped or recorded as a redacted render-drop/error
- **AND** it does not raise a cross-thread or use-after-unmount error.

### Requirement: Default TUI DOM shall remain opencode-like

The production control-plane change SHALL preserve the single output-stream and
single-composer default model.

#### Scenario: App mounts

- **WHEN** `vnalpha tui` starts
- **THEN** exactly one `OutputStream` is mounted
- **AND** exactly one `ComposerInput` is mounted
- **AND** exactly one Textual `Input` exists in the default DOM
- **AND** no `ContentSwitcher` is mounted in the default path
- **AND** no persistent secondary `ChatPanel` is mounted in the default path.

### Requirement: Read-only research boundary shall be preserved

The production control plane SHALL not introduce trading execution or arbitrary
mutation capabilities.

#### Scenario: Disallowed request or unsafe operational value is submitted

- **WHEN** a request implies broker, order, account, portfolio, margin,
  transfer, allocation, trading execution, arbitrary shell, source edit, Git,
  GitHub, remote deployment, path traversal, or command injection behavior
- **THEN** the system refuses or reports unsupported behavior
- **AND** logs the refusal with redaction
- **AND** does not create, route, or execute the unsafe action.

#### Scenario: Allowed local research evidence is written

- **WHEN** a valid control-plane action writes audit data, a repair bundle, or
  local research-artifact state
- **THEN** it remains inside the read-only research boundary
- **AND** redaction occurs before persistence
- **AND** the action does not access broker or trading systems.

### Requirement: Validation evidence shall be reproducible

The implementation SHALL record validation run from the repository root using
isolated warehouse and log paths.

#### Scenario: Feature validation runs

- **WHEN** implementation is ready for validation
- **THEN** targeted TUI tests, `make test-vnalpha`, `make lint-vnalpha`,
  `make verify-r4`, and `packaging/scripts/openstock-verify --ci` are run from
  the OpenStock worktree root
- **AND** `VNALPHA_WAREHOUSE_PATH` and `VNALPHA_LOG_ROOT` point to isolated
  temporary paths
- **AND** the recorded evidence states any unavailable external prerequisite.
