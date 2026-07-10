# Tasks: Safe Tools Auto-Execute Policy and TUI Command Lifecycle

## 0. Governance

- [x] 0.1 Preserve OpenStock as a research-only workspace.
- [x] 0.2 Preserve the read-only research boundary: do not add broker/order/account/portfolio/margin/trading execution.
- [x] 0.3 Treat all tools in `SAFE_TOOLS` as trusted and auto-executable.
- [x] 0.4 Refuse any tool not present in `SAFE_TOOLS`.
- [x] 0.5 Hard-deny forbidden trading/account/broker tool names and prefixes.
- [x] 0.6 Preserve redaction-by-default logging.
- [x] 0.7 Preserve closed-loop logging behavior.

## 1. Single SAFE_TOOLS source of truth

- [x] 1.1 Add `vnalpha.assistant.tool_policy`.
- [x] 1.2 Define `SAFE_TOOLS` as the single source of truth for assistant/TUI auto-executable tools.
- [x] 1.3 Include current trusted tools: `watchlist.scan`, `watchlist.filter`, `candidate.compare`, `candidate.explain`, `quality.get_status`, `quality.get_many_status`, `lineage.get_symbol_lineage`, `history.list_sessions`, `note.create`, `data.fetch`.
- [x] 1.4 Define `FORBIDDEN_TOOL_PREFIXES` for broker/order/account/portfolio/margin/trading execution boundaries.
- [x] 1.5 Define `FORBIDDEN_TOOL_NAMES` for explicit execution/account/broker operations.
- [x] 1.6 Implement `is_forbidden_tool(tool_name)`.
- [x] 1.7 Implement `is_safe_tool(tool_name)`.
- [x] 1.8 Implement `assert_safe_tool(tool_name)`.
- [x] 1.9 Implement `is_safe_plan(plan)`.
- [x] 1.10 Implement `unsafe_tools_in_plan(plan)`.

## 2. Planner policy integration

- [x] 2.1 Remove or deprecate planner-local `TOOL_ALLOWLIST`.
- [x] 2.2 Validate plan steps using `is_safe_tool()`.
- [x] 2.3 Ensure planner refuses unknown/non-safe tools.
- [x] 2.4 Ensure planner hard-denies forbidden trading/account/broker tools.
- [x] 2.5 Add tests proving planner uses `SAFE_TOOLS` rather than independent allowlist.

## 3. Executor policy integration

- [x] 3.1 Remove or deprecate executor-local `ASSISTANT_TOOL_ALLOWLIST`.
- [x] 3.2 Validate every tool step with `assert_safe_tool()` immediately before execution.
- [x] 3.3 Ensure executor refuses unknown/non-safe tools even if planner missed them.
- [x] 3.4 Ensure executor hard-denies forbidden trading/account/broker tools.
- [x] 3.5 Add tests proving executor uses the same `SAFE_TOOLS` policy.

## 4. Chat execution semantics

- [x] 4.1 Replace `is_safe_read_only_plan()` semantics with `is_safe_plan()` semantics.
- [x] 4.2 Either rename `AUTO_EXECUTE_SAFE_READ_ONLY` to `AUTO_EXECUTE_SAFE_TOOLS`, or document/deprecate the old name while changing semantics.
- [x] 4.3 In auto mode, execute every plan whose steps are all in `SAFE_TOOLS`.
- [x] 4.4 In auto mode, do not require approval for `note.create`.
- [x] 4.5 In auto mode, do not require approval for `data.fetch`.
- [x] 4.6 In auto mode, refuse any plan containing tools outside `SAFE_TOOLS`.
- [x] 4.7 Preserve `PLAN_ONLY` behavior if retained.
- [x] 4.8 Remove obsolete approval-gate logic unless still used for explicit future UX.
- [x] 4.9 Add tests for `note.create` auto-execution.
- [x] 4.10 Add tests for `data.fetch` auto-execution.
- [x] 4.11 Add tests for unknown tool refusal.
- [x] 4.12 Add tests for broker/order/account/portfolio/margin/trading hard-deny.

## 5. TUI operational command bridge

- [x] 5.1 Add explicit TUI route for `/logs ...` before generic research slash command routing.
- [x] 5.2 Add explicit TUI route for `/repair ...` before generic research slash command routing.
- [x] 5.3 Add explicit TUI route for `/deploy ...` before generic research slash command routing.
- [x] 5.4 Support `/logs errors --latest`.
- [x] 5.5 Support `/logs summarize --latest`.
- [x] 5.6 Support `/repair prepare --latest`.
- [x] 5.7 Support `/repair status <repair-id>`.
- [x] 5.8 Support `/deploy verify <candidate>`.
- [x] 5.9 Support `/deploy promote <candidate> --deployment-id <id>`.
- [x] 5.10 Support `/deploy rollback <deployment-id>`.
- [x] 5.11 Unsupported operational subcommands must render a clear inline unsupported message.
- [x] 5.12 Operational commands must not fall through to research `CommandExecutor` registry.
- [x] 5.13 Add routing tests for `/logs`, `/repair`, `/deploy`.

## 6. TUI command lifecycle observability

- [x] 6.1 Wrap TUI research slash command execution in `command_lifecycle()`.
- [x] 6.2 Wrap TUI operational command execution in `command_lifecycle()`.
- [x] 6.3 Ensure `COMMAND_STARTED` is emitted.
- [x] 6.4 Ensure `COMMAND_SUCCEEDED` is emitted on success.
- [x] 6.5 Ensure `COMMAND_FAILED` is emitted on failure.
- [x] 6.6 Ensure `capture_exception()` is called on command exception.
- [x] 6.7 Ensure correlation ID is non-empty and not `unset`.
- [x] 6.8 Preserve redaction-by-default command args logging.
- [x] 6.9 Add tests validating command lifecycle events for TUI slash command.
- [x] 6.10 Add tests validating command lifecycle events for TUI operational command.

## 7. TUI resource lifecycle

- [x] 7.1 Store command DuckDB connection on `TuiInputRouter`, e.g. `self._command_conn`.
- [x] 7.2 Add `TuiInputRouter.close()`.
- [x] 7.3 Ensure `close()` closes `_command_conn` once and nulls it.
- [x] 7.4 Add `VnAlphaApp.on_unmount()` or equivalent lifecycle hook to call router close.
- [x] 7.5 Add tests proving command connection is closed on router/app shutdown.

## 8. Textual thread-safety

- [x] 8.1 Introduce a TUI UI dispatcher or Textual message-based rendering path.
- [x] 8.2 Ensure `ChatController` callbacks do not directly update Textual widgets from worker thread.
- [x] 8.3 Marshal assistant messages onto Textual app loop.
- [x] 8.4 Marshal trace events onto Textual app loop.
- [x] 8.5 Marshal status updates onto Textual app loop where required.
- [x] 8.6 Add headless smoke test proving chat callback renders without cross-thread UI errors.

## 9. Documentation and tests alignment

- [x] 9.1 Update `vnalpha/docs/tui-workspace.md` to describe `SAFE_TOOLS` auto-execute semantics.
- [x] 9.2 Update docs to clearly state no broker/order/account/portfolio/margin/trading execution.
- [x] 9.3 Update docs for `/logs`, `/repair`, `/deploy` only after implementation or mark unsupported subcommands clearly.
- [x] 9.4 Fix or remove `vnalpha tui --smoke` docs/test claim.
- [x] 9.5 Strengthen TUI router tests to exercise real `_setup_executor` with mocked/in-memory DuckDB connection.
- [x] 9.6 Remove tests that pass merely because CLI help exits successfully.

## 10. Validation

- [x] 10.1 Run `make test-vnalpha`.
- [x] 10.2 Run `make lint-vnalpha`.
- [x] 10.3 Run `make verify-r4`.
- [x] 10.4 Run `openstock-verify --ci`.
- [x] 10.5 Attach validation output to PR or implementation notes.

## 11. Acceptance checklist

- [x] 11.1 There is exactly one `SAFE_TOOLS` source of truth.
- [x] 11.2 `note.create` auto-executes when planned.
- [x] 11.3 `data.fetch` auto-executes when planned.
- [x] 11.4 Unknown tools are refused.
- [x] 11.5 Broker/order/account/portfolio/margin/trading tools are hard-denied.
- [x] 11.6 `/logs`, `/repair`, `/deploy` are explicitly routed.
- [x] 11.7 TUI slash and operational commands emit lifecycle events.
- [x] 11.8 TUI worker-thread callbacks are Textual-safe.
- [x] 11.9 TUI router closes DuckDB command connection on shutdown.
- [x] 11.10 Docs no longer overclaim unimplemented behavior.

## Validation Evidence

- `VNALPHA_WAREHOUSE_PATH=/tmp/openstock-vnalpha-full-test.duckdb make test-vnalpha` — passed.
- `make lint-vnalpha` — passed (`ruff check .` and `ruff format --check .`).
- `VNALPHA_WAREHOUSE_PATH=/tmp/openstock-vnalpha-r4-final-test.duckdb make verify-r4` — passed.
- `VNALPHA_WAREHOUSE_PATH=/tmp/openstock-vnalpha-verify-final-test.duckdb ../packaging/scripts/openstock-verify --ci` — passed (13 OK, 1 non-failing systemd warning).
- Focused policy, chat, TUI routing, lifecycle, thread-dispatch, and documentation tests passed before the full-suite gate.
