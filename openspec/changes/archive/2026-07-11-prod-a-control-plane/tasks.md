# Tasks: Production control plane for opencode-like auto research

## 0. Governance

- [x] 0.1 Keep the system inside the read-only research boundary.
- [x] 0.2 Do not introduce broker, order, account, portfolio, margin, transfer, allocation, or trading execution tools.
- [x] 0.3 Preserve redaction-by-default logging.
- [x] 0.4 Preserve closed-loop logging artifacts.
- [x] 0.5 Do not reintroduce `ContentSwitcher` or persistent secondary `ChatPanel` into the default TUI path.
- [x] 0.6 Do not mark implementation complete without validation evidence.

## 1. Router executor setup

- [x] 1.1 Update `TuiInputRouter._setup_executor()` to open a DuckDB connection with `get_connection()`.
- [x] 1.2 Run `run_migrations(conn=conn)` before constructing the command executor.
- [x] 1.3 Instantiate `CommandExecutor(conn, surface="tui", default_date=self._target_date)`.
- [x] 1.4 Store the connection on the router instance, e.g. `self._command_conn`.
- [x] 1.5 Add a router/app shutdown hook that closes the owned connection.
- [x] 1.6 Render setup failure inline with an actionable error, not only `CommandExecutor unavailable.`.
- [x] 1.7 Capture setup exceptions via `capture_exception()`.

## 2. Operational command bridge

- [x] 2.1 Add explicit routing before generic slash command for `/logs`.
- [x] 2.2 Support `/logs errors --latest`.
- [x] 2.3 Support `/logs summarize --latest`.
- [x] 2.4 Add explicit routing before generic slash command for `/repair`.
- [x] 2.5 Support `/repair prepare --latest`.
- [x] 2.6 Support `/repair status <repair-id>`.
- [x] 2.7 Add explicit routing before generic slash command for `/deploy`.
- [x] 2.8 Support `/deploy verify <candidate>`.
- [x] 2.9 Support `/deploy promote <candidate> --deployment-id <id>` as research artifact promotion only.
- [x] 2.10 Support `/deploy rollback <deployment-id>` as research artifact rollback only.
- [x] 2.11 Render clear unsupported messages for unsupported subcommands.
- [x] 2.12 Add docs that `/deploy` is not broker/trading deployment.

## 3. Command lifecycle observability

- [x] 3.1 Generate a non-empty correlation ID for every non-empty TUI submission.
- [x] 3.2 Emit `TUI_INPUT_SUBMITTED` for every non-empty TUI submission.
- [x] 3.3 Emit `TUI_COMMAND_ROUTED` for slash commands.
- [x] 3.4 Emit `COMMAND_STARTED` before command/operational command execution.
- [x] 3.5 Emit `COMMAND_SUCCEEDED` after successful command/operational command execution.
- [x] 3.6 Emit `COMMAND_FAILED` after failed command/operational command execution.
- [x] 3.7 Capture exceptions via `capture_exception()`.
- [x] 3.8 Ensure command logs preserve redaction-by-default.

## 4. Thread-safe rendering

- [x] 4.1 Audit ChatController callbacks used by TUI router.
- [x] 4.2 Replace direct worker-thread widget writes with Textual-safe marshaling.
- [x] 4.3 Ensure assistant messages render through the safe UI path.
- [x] 4.4 Ensure tool trace events render through the safe UI path.
- [x] 4.5 Ensure errors/warnings render through the safe UI path.
- [x] 4.6 Add a headless smoke test proving chat callback rendering does not raise cross-thread UI errors.

## 5. Tests

- [x] 5.1 Add test: real `_setup_executor()` works with mocked or in-memory DuckDB connection.
- [x] 5.2 Add test: `/help` via TUI router renders command result into OutputStream.
- [x] 5.3 Add test: `/logs errors --latest` routes through operational bridge.
- [x] 5.4 Add test: `/repair prepare --latest` routes through operational bridge.
- [x] 5.5 Add test: `/deploy verify <candidate>` routes through operational bridge.
- [x] 5.6 Add test: TUI slash command emits lifecycle observability event.
- [x] 5.7 Remove or tighten weak smoke-flag assertions that pass without real `--smoke` support.
- [x] 5.8 Add regression test: default TUI path has exactly one `Input`.
- [x] 5.9 Add regression test: no `ContentSwitcher` in default TUI path.
- [x] 5.10 Add regression test: no persistent secondary `ChatPanel` in default TUI path.

## 6. Documentation

- [x] 6.1 Update `vnalpha/docs/tui-workspace.md` to match implemented command bridge behavior.
- [x] 6.2 Document command lifecycle events.
- [x] 6.3 Document router connection lifecycle.
- [x] 6.4 Document read-only research boundary for TUI operational commands.

## 7. Validation

- [x] 7.1 Run `make test-vnalpha`.
- [x] 7.2 Run `make lint-vnalpha`.
- [x] 7.3 Run `make verify-r4`.
- [x] 7.4 Run `openstock-verify --ci`.
- [x] 7.5 Attach validation evidence to the PR before merge.

## Validation evidence

- `VNALPHA_WAREHOUSE_PATH=/tmp/opencode/vnalpha-prod-control-plane-<pid>.duckdb make test-vnalpha`: passed.
- `make lint-vnalpha`: Ruff clean; 318 files format-clean.
- `make verify-r4`: passed.
- `./packaging/scripts/openstock-verify --ci`: PASS (16 OK, 1 existing systemd warning, 0 failures).
- Focused control-plane suite: `tests/test_tui_control_plane.py`, `test_tui_operational_router.py`, and `test_tui_thread_dispatch.py` passed.
- No PR was requested or exists in this workspace; PR attachment was waived by explicit user direction when this change was marked complete.
