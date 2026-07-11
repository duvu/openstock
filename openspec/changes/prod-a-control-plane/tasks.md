# Tasks: Production control plane for opencode-like auto research

## 0. Governance and scope

- [x] 0.1 Implement only in `vnalpha/` from an isolated OpenStock worktree.
- [x] 0.2 Preserve the read-only research boundary; do not add broker, order,
  account, portfolio, margin, transfer, allocation, trading execution,
  arbitrary shell, source-edit, Git, GitHub, or remote-deployment capability.
- [x] 0.3 Keep Phase A as TUI bridge/control-plane glue; do not reimplement
  Phase D repair, validation, promotion, or rollback state machines.
- [x] 0.4 Preserve redaction-by-default for all persisted evidence.
- [x] 0.5 Preserve the one-output/one-composer DOM and no default
  `ContentSwitcher` or persistent `ChatPanel`.
- [ ] 0.6 Do not mark this change complete without recorded validation evidence.

## 1. Characterize the current router with failing tests

- [x] 1.1 Add a failing test proving a real in-memory DuckDB connection is
  migrated and retained by `TuiInputRouter` before `/help` executes.
- [x] 1.2 Add a failing test proving setup failure closes a partially opened
  connection, records `TUI_COMMAND_SETUP_FAILED`, and renders an actionable
  redacted command-degraded message while chat remains available.
- [x] 1.3 Add a failing test proving a returned `FAILED` result produces
  `COMMAND_FAILED` rather than `COMMAND_SUCCEEDED`.
- [x] 1.4 Add a failing test proving a returned `VALIDATION_ERROR` produces
  `COMMAND_FAILED` rather than `COMMAND_SUCCEEDED`.
- [x] 1.5 Add a failing test proving a raised research-command exception emits
  `COMMAND_FAILED`, captures an error record, and redacts a fixture secret.
- [ ] 1.6 Run the focused tests and confirm each fails for the intended missing
  behavior before changing production code.

## 2. Router-owned executor and shutdown lifecycle

- [x] 2.1 Extend the executor setup result so it carries a safe setup failure
  reason without retaining an unusable connection.
- [x] 2.2 Make `LifecycleHooks.setup_executor()` open the connection, run
  migrations, construct `CommandExecutor(conn, surface="tui",
  default_date=target_date)`, and retain the exact connection on success.
- [x] 2.3 On setup failure, call `capture_exception()`, emit the redacted setup
  event, close the partial connection, and expose a safe router error state.
- [x] 2.4 Make the generic command path display the safe actionable setup
  error instead of the generic unavailable message.
- [x] 2.5 Add explicit router state for accepting, active, close-requested, and
  closed lifetimes.
- [x] 2.6 Make `close()` reject future work, defer close while a route is
  active, and close the owned connection exactly once after the route exits.
- [x] 2.7 Wire app unmount to the router shutdown contract and prove no active
  route can observe a closed DuckDB connection.
- [x] 2.8 Run the executor/setup/shutdown focused tests and confirm they pass.

## 3. Single-flight admission and submission identity

- [x] 3.1 Add a failing async test with a blocking executor proving a second
  command is rejected while the first still owns the connection.
- [x] 3.2 Add a failing test proving busy `/approve`, `/cancel`, and `/clear`
  do not mutate `ChatController` or widgets concurrently.
- [x] 3.3 Add a failing test proving shutdown rejects a new submission and does
  not restart an executor or operational action.
- [x] 3.4 Generate a fresh correlation ID at the router entry point for every
  non-empty submission before rendering, audit, or worker dispatch.
- [x] 3.5 Emit redacted `TUI_INPUT_SUBMITTED` metadata with input kind and
  length, then route/rejection events with that same ID.
- [x] 3.6 Implement deterministic busy/closing rejection with an inline warning
  and `TUI_INPUT_REJECTED`, without invoking executor, chat, or bridge code.
- [x] 3.7 Route accepted control commands through `TUI_CONTROL_ROUTED`; do not
  emit command-start events for controls or rejections.
- [x] 3.8 Run the admission/correlation focused tests and confirm they pass.

## 4. Truthful command lifecycle evidence

- [x] 4.1 Add a result-aware command lifecycle helper or equivalent explicit
  writer that maps `SUCCESS`, `EMPTY_RESULT`, and `PARTIAL` to completion and
  maps `FAILED` and `VALIDATION_ERROR` to failure.
- [x] 4.2 Update generic slash-command routing to emit the ordered command
  lifecycle and render all returned results inline.
- [x] 4.3 Update operational routing to use the same lifecycle and capture
  raised domain failures.
- [x] 4.4 Persist `TUI_RENDER_ERROR` before/with captured rendering exceptions,
  keeping the current submission correlation ID.
- [x] 4.5 Verify audit, command, and error records share the new submission ID
  and contain no raw fixture secret.
- [x] 4.6 Run the lifecycle/redaction focused tests and confirm they pass.

## 5. Strict operational bridge

- [x] 5.1 Add failing bridge tests for all seven documented forms and prove
  each bypasses the research `CommandExecutor`.
- [x] 5.2 Add failing bridge tests rejecting extra options, reordered options,
  empty values, path separators, traversal values, and shell-like identifier
  values without calling a domain action.
- [x] 5.3 Add a strict opaque identifier validator for repair IDs, candidates,
  and deployment IDs.
- [x] 5.4 Resolve `--latest` once at execution start and pass the resolved run
  identity through the relevant action rather than accepting a path from input.
- [x] 5.5 Keep the bridge as a delegate: call existing observability/Phase D
  domain functions and do not duplicate promotion, rollback, or validation
  gate semantics.
- [x] 5.6 Render invalid grammar, unsupported forms, and domain-gate blocks as
  redacted inline errors with `COMMAND_FAILED` evidence.
- [x] 5.7 Document in code and tests that `/deploy` is research-artifact-only
  and cannot execute a broker or trading action.
- [x] 5.8 Run the operational bridge focused tests and confirm they pass.

## 6. Textual-safe worker callbacks

- [x] 6.1 Add failing tests for assistant-message, trace, warning, and error
  callbacks invoked from a worker-context simulation.
- [x] 6.2 Require a live UI dispatcher for worker-originated callbacks; remove
  any direct-widget fallback from that path.
- [x] 6.3 Make `VnAlphaApp` provide a dispatcher that routes callback work onto
  the Textual app loop while the app is mounted.
- [x] 6.4 Deactivate the dispatcher at unmount and safely record/drop late
  callbacks without use-after-unmount or cross-thread widget mutation.
- [x] 6.5 Add a headless app test proving worker callbacks render after an app
  loop tick and a late callback does not raise.
- [x] 6.6 Run the thread-safety focused tests and confirm they pass.

## 7. Default DOM and documentation

- [x] 7.1 Preserve or add regression tests for one `OutputStream`, one
  `ComposerInput`, one Textual `Input`, no default `ContentSwitcher`, and no
  persistent default `ChatPanel`.
- [x] 7.2 Update `vnalpha/docs/tui-workspace.md` with the strict seven-form
  grammar, busy policy, router connection lifetime, lifecycle table,
  correlation behavior, and Phase A/Phase D boundary.
- [x] 7.3 Document that local logs/bundles/artifact metadata are permitted
  evidence writes but source/Git/remote/trading mutations are not.
- [x] 7.4 Remove stale validation claims and state root workdir plus isolated
  warehouse/log environment for every validation command.

## 8. Validation and evidence

- [x] 8.1 Run the targeted router, operational bridge, lifecycle, and TUI
  callback tests with isolated `VNALPHA_WAREHOUSE_PATH` and `VNALPHA_LOG_ROOT`.
- [ ] 8.2 Run `make test-vnalpha` from the OpenStock worktree root with isolated
  warehouse/log paths.
- [ ] 8.3 Run `make lint-vnalpha` from the OpenStock worktree root.
- [x] 8.4 Run `make verify-r4` from the OpenStock worktree root and document any
  pre-existing unrelated failure before proceeding.
- [x] 8.5 Run `packaging/scripts/openstock-verify --ci` from the OpenStock
  worktree root.
- [x] 8.6 Add `validation.md` with exact commands, environment isolation, exit
  status, test totals, and any known non-blocking warnings.
