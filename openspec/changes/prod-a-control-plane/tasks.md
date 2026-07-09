# Tasks: Production control plane for opencode-like auto research

## 0. Governance

- [ ] 0.1 Keep the system inside the read-only research boundary.
- [ ] 0.2 Do not introduce broker, order, account, portfolio, margin, transfer, allocation, or trading execution tools.
- [ ] 0.3 Preserve redaction-by-default logging.
- [ ] 0.4 Preserve closed-loop logging artifacts.
- [ ] 0.5 Do not reintroduce `ContentSwitcher` or persistent secondary `ChatPanel` into the default TUI path.
- [ ] 0.6 Do not mark implementation complete without validation evidence.

## 1. Router executor setup

- [ ] 1.1 Update `TuiInputRouter._setup_executor()` to open a DuckDB connection with `get_connection()`.
- [ ] 1.2 Run `run_migrations(conn=conn)` before constructing the command executor.
- [ ] 1.3 Instantiate `CommandExecutor(conn, surface="tui", default_date=self._target_date)`.
- [ ] 1.4 Store the connection on the router instance, e.g. `self._command_conn`.
- [ ] 1.5 Add a router/app shutdown hook that closes the owned connection.
- [ ] 1.6 Render setup failure inline with an actionable error, not only `CommandExecutor unavailable.`.
- [ ] 1.7 Capture setup exceptions via `capture_exception()`.

## 2. Operational command bridge

- [ ] 2.1 Add explicit routing before generic slash command for `/logs`.
- [ ] 2.2 Support `/logs errors --latest`.
- [ ] 2.3 Support `/logs summarize --latest`.
- [ ] 2.4 Add explicit routing before generic slash command for `/repair`.
- [ ] 2.5 Support `/repair prepare --latest`.
- [ ] 2.6 Support `/repair status <repair-id>`.
- [ ] 2.7 Add explicit routing before generic slash command for `/deploy`.
- [ ] 2.8 Support `/deploy verify <candidate>`.
- [ ] 2.9 Support `/deploy promote <candidate> --deployment-id <id>` as research artifact promotion only.
- [ ] 2.10 Support `/deploy rollback <deployment-id>` as research artifact rollback only.
- [ ] 2.11 Render clear unsupported messages for unsupported subcommands.
- [ ] 2.12 Add docs that `/deploy` is not broker/trading deployment.

## 3. Command lifecycle observability

- [ ] 3.1 Generate a non-empty correlation ID for every non-empty TUI submission.
- [ ] 3.2 Emit `TUI_INPUT_SUBMITTED` for every non-empty TUI submission.
- [ ] 3.3 Emit `TUI_COMMAND_ROUTED` for slash commands.
- [ ] 3.4 Emit `COMMAND_STARTED` before command/operational command execution.
- [ ] 3.5 Emit `COMMAND_SUCCEEDED` after successful command/operational command execution.
- [ ] 3.6 Emit `COMMAND_FAILED` after failed command/operational command execution.
- [ ] 3.7 Capture exceptions via `capture_exception()`.
- [ ] 3.8 Ensure command logs preserve redaction-by-default.

## 4. Thread-safe rendering

- [ ] 4.1 Audit ChatController callbacks used by TUI router.
- [ ] 4.2 Replace direct worker-thread widget writes with Textual-safe marshaling.
- [ ] 4.3 Ensure assistant messages render through the safe UI path.
- [ ] 4.4 Ensure tool trace events render through the safe UI path.
- [ ] 4.5 Ensure errors/warnings render through the safe UI path.
- [ ] 4.6 Add a headless smoke test proving chat callback rendering does not raise cross-thread UI errors.

## 5. Tests

- [ ] 5.1 Add test: real `_setup_executor()` works with mocked or in-memory DuckDB connection.
- [ ] 5.2 Add test: `/help` via TUI router renders command result into OutputStream.
- [ ] 5.3 Add test: `/logs errors --latest` routes through operational bridge.
- [ ] 5.4 Add test: `/repair prepare --latest` routes through operational bridge.
- [ ] 5.5 Add test: `/deploy verify <candidate>` routes through operational bridge.
- [ ] 5.6 Add test: TUI slash command emits lifecycle observability event.
- [ ] 5.7 Remove or tighten weak smoke-flag assertions that pass without real `--smoke` support.
- [ ] 5.8 Add regression test: default TUI path has exactly one `Input`.
- [ ] 5.9 Add regression test: no `ContentSwitcher` in default TUI path.
- [ ] 5.10 Add regression test: no persistent secondary `ChatPanel` in default TUI path.

## 6. Documentation

- [ ] 6.1 Update `vnalpha/docs/tui-workspace.md` to match implemented command bridge behavior.
- [ ] 6.2 Document command lifecycle events.
- [ ] 6.3 Document router connection lifecycle.
- [ ] 6.4 Document read-only research boundary for TUI operational commands.

## 7. Validation

- [ ] 7.1 Run `make test-vnalpha`.
- [ ] 7.2 Run `make lint-vnalpha`.
- [ ] 7.3 Run `make verify-r4`.
- [ ] 7.4 Run `openstock-verify --ci`.
- [ ] 7.5 Attach validation evidence to the PR before merge.
