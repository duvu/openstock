# Tasks: TUI history and operational polish

## 0. Governance

- [x] 0.1 Preserve the opencode-like default TUI model.
- [x] 0.2 Do not reintroduce `ContentSwitcher` in the default path.
- [x] 0.3 Do not reintroduce a secondary `ChatPanel` below the output stream.
- [x] 0.4 Do not add a separate command history pane.
- [x] 0.5 Do not add a separate command result pane.
- [x] 0.6 Keep exactly one primary composer input in the default TUI.
- [x] 0.7 Keep exactly one primary output stream in the default TUI.
- [x] 0.8 Preserve closed-loop observability.
- [x] 0.9 Preserve the read-only research boundary.
- [x] 0.10 Do not mark complete without tests and validation evidence.

## 1. Input history model

- [x] 1.1 Add `vnalpha/src/vnalpha/tui/input_history.py`.
- [x] 1.2 Implement `InputHistory.push(text)`.
- [x] 1.3 Implement `InputHistory.previous(current_draft)`.
- [x] 1.4 Implement `InputHistory.next()`.
- [x] 1.5 Implement `InputHistory.reset_navigation()`.
- [x] 1.6 Ignore empty and whitespace-only inputs.
- [x] 1.7 Deduplicate consecutive identical inputs.
- [x] 1.8 Enforce bounded max history size.
- [x] 1.9 Preserve current draft while navigating history.
- [x] 1.10 Restore draft after moving past newest history item.
- [x] 1.11 Add unit tests for all history edge cases.

## 2. ComposerInput integration

- [x] 2.1 Add an `InputHistory` instance to ComposerInput or inject one from the app.
- [x] 2.2 Bind Up to previous history item.
- [x] 2.3 Bind Down to next history item.
- [x] 2.4 Optionally bind Ctrl+P to previous history item.
- [x] 2.5 Optionally bind Ctrl+N to next history item.
- [x] 2.6 Push submitted non-empty text into history.
- [x] 2.7 Reset history navigation after submit.
- [x] 2.8 Reset history navigation when user types new text manually.
- [x] 2.9 Ensure history works for slash commands.
- [x] 2.10 Ensure history works for natural-language input.
- [x] 2.11 Ensure history works for chat-local commands.
- [x] 2.12 Add headless TUI tests for Up/Down behavior.

## 3. Optional persistent history

- [x] 3.1 Decide whether implementation includes persisted history in this PR.
- [x] 3.2 If persistence is deferred, document that history is in-session only.
- [x] 3.3 If implemented, add bounded JSONL or warehouse-backed persistence.
- [x] 3.4 Add config/env flag to disable persisted history.
- [x] 3.5 Apply redaction/sensitive-pattern skip rules.
- [x] 3.6 Do not store empty input.
- [x] 3.7 Do not store raw secrets/tokens/cookies.
- [x] 3.8 Add tests for persisted history if implemented.

## 4. Runtime status model

- [x] 4.1 Add `vnalpha/src/vnalpha/tui/runtime_status.py`.
- [x] 4.2 Define `RuntimeState` enum or equivalent constants.
- [x] 4.3 Define `RuntimeStatus` dataclass or equivalent model.
- [x] 4.4 Include current state, label, detail, started_at, last_error.
- [x] 4.5 Add state transition helper.
- [x] 4.6 Add tests for status model transitions.

## 5. Status bar widget

- [x] 5.1 Add `vnalpha/src/vnalpha/tui/widgets/status_bar.py`.
- [x] 5.2 Render compact one-line status.
- [x] 5.3 Show IDLE/READY state.
- [x] 5.4 Show command-running state.
- [x] 5.5 Show chat-thinking state.
- [x] 5.6 Show tool-running state.
- [x] 5.7 Show data-ensure/sync/build/score states.
- [x] 5.8 Show warning state.
- [x] 5.9 Show error state.
- [x] 5.10 Show service-unavailable state where detected.
- [x] 5.11 Keep status bar compact and non-primary.
- [x] 5.12 Add tests for status bar text rendering.

## 6. App/router status integration

- [x] 6.1 Wire status bar into `VnAlphaApp` without breaking layout constraints.
- [x] 6.2 Set `ROUTING_INPUT` when input submission starts.
- [x] 6.3 Set `COMMAND_RUNNING` for slash command route.
- [x] 6.4 Set `CHAT_THINKING` for natural-language route.
- [x] 6.5 Set `TOOL_RUNNING` on tool trace running events.
- [x] 6.6 Set data provisioning states during `/explain` and assistant data ensure flows where feasible.
- [x] 6.7 Set `READY` after successful completion.
- [x] 6.8 Set `WARNING` when result has warnings but no hard failure.
- [x] 6.9 Set `ERROR` when route/render/command/chat fails.
- [x] 6.10 Ensure status is reset or updated after cancellation.
- [x] 6.11 Add tests for route-driven status transitions.

## 7. OutputStream visual polish

- [x] 7.1 Standardize user message block rendering.
- [x] 7.2 Standardize assistant message block rendering.
- [x] 7.3 Standardize command result block rendering.
- [x] 7.4 Standardize tool trace block rendering.
- [x] 7.5 Standardize data readiness/provisioning block rendering if applicable.
- [x] 7.6 Standardize warning block rendering.
- [x] 7.7 Standardize error block rendering.
- [x] 7.8 Use compact labels consistently.
- [x] 7.9 Avoid excessive vertical noise.
- [x] 7.10 Keep markup robust when text contains brackets/special characters.
- [x] 7.11 Add tests for semantic output methods.

## 8. Footer/keybinding hints

- [x] 8.1 Add or update compact footer hint.
- [x] 8.2 Include `Enter submit`.
- [x] 8.3 Include `Up/Down history`.
- [x] 8.4 Include `Ctrl+L clear`.
- [x] 8.5 Include `/help commands`.
- [x] 8.6 Include `Esc cancel/clear`.
- [x] 8.7 Keep footer compact and non-primary.
- [x] 8.8 Add tests only for content presence, not exact styling.

## 9. Operational states for auto data provisioning

- [x] 9.1 Show visible state when ensure-data starts.
- [x] 9.2 Show visible state when OHLCV sync starts.
- [x] 9.3 Show visible state when benchmark sync starts.
- [x] 9.4 Show visible state when canonical build starts.
- [x] 9.5 Show visible state when feature build starts.
- [x] 9.6 Show visible state when scoring starts.
- [x] 9.7 Show visible READY when data ensure succeeds.
- [x] 9.8 Show visible WARNING when data ensure is partial.
- [x] 9.9 Show visible ERROR when data ensure fails.
- [x] 9.10 Add tests or documented adapter behavior for data provisioning states.

## 10. Observability

- [x] 10.1 Emit `TUI_HISTORY_PUSHED` or equivalent.
- [x] 10.2 Emit `TUI_HISTORY_PREVIOUS` or equivalent.
- [x] 10.3 Emit `TUI_HISTORY_NEXT` or equivalent.
- [x] 10.4 Emit `TUI_HISTORY_DRAFT_RESTORED` or equivalent.
- [x] 10.5 Emit `TUI_STATUS_CHANGED` or equivalent.
- [x] 10.6 Avoid logging raw full input unless redacted.
- [x] 10.7 Log input kind and length instead of raw sensitive content where possible.
- [x] 10.8 Add tests or mocks proving observability hooks are called.

## 11. Layout regression tests

- [x] 11.1 Assert exactly one `ComposerInput` in default app.
- [x] 11.2 Assert exactly one primary `OutputStream` in default app.
- [x] 11.3 Assert exactly one Textual `Input` in default app.
- [x] 11.4 Assert no `ContentSwitcher` in default path.
- [x] 11.5 Assert no secondary `ChatPanel` in default path.
- [x] 11.6 Assert no `CommandScreen` in default workflow.
- [x] 11.7 Assert status/footer widgets, if present, are supporting widgets.

## 12. Documentation

- [x] 12.1 Update `vnalpha/docs/tui-workspace.md`.
- [x] 12.2 Document Up/Down history.
- [x] 12.3 Document Ctrl+P/Ctrl+N if implemented.
- [x] 12.4 Document status states.
- [x] 12.5 Document data provisioning status messages.
- [x] 12.6 Document visible clear vs persisted audit/history.
- [x] 12.7 Document how to diagnose ERROR/SERVICE_UNAVAILABLE.

## 13. Validation

- [x] 13.1 Run `make test-vnalpha`.
- [x] 13.2 Run `make lint-vnalpha`.
- [x] 13.3 Run `make verify-r4`.
- [x] 13.4 Run `openstock-verify --ci`.
- [x] 13.5 Add validation evidence for Up/Down history.
- [x] 13.6 Add validation evidence for status transitions.
- [x] 13.7 Add validation evidence that default layout constraints still pass.
