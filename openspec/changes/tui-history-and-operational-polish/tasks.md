# Tasks: TUI history and operational polish

## 0. Governance

- [ ] 0.1 Preserve the opencode-like default TUI model.
- [ ] 0.2 Do not reintroduce `ContentSwitcher` in the default path.
- [ ] 0.3 Do not reintroduce a secondary `ChatPanel` below the output stream.
- [ ] 0.4 Do not add a separate command history pane.
- [ ] 0.5 Do not add a separate command result pane.
- [ ] 0.6 Keep exactly one primary composer input in the default TUI.
- [ ] 0.7 Keep exactly one primary output stream in the default TUI.
- [ ] 0.8 Preserve closed-loop observability.
- [ ] 0.9 Preserve the read-only research boundary.
- [ ] 0.10 Do not mark complete without tests and validation evidence.

## 1. Input history model

- [ ] 1.1 Add `vnalpha/src/vnalpha/tui/input_history.py`.
- [ ] 1.2 Implement `InputHistory.push(text)`.
- [ ] 1.3 Implement `InputHistory.previous(current_draft)`.
- [ ] 1.4 Implement `InputHistory.next()`.
- [ ] 1.5 Implement `InputHistory.reset_navigation()`.
- [ ] 1.6 Ignore empty and whitespace-only inputs.
- [ ] 1.7 Deduplicate consecutive identical inputs.
- [ ] 1.8 Enforce bounded max history size.
- [ ] 1.9 Preserve current draft while navigating history.
- [ ] 1.10 Restore draft after moving past newest history item.
- [ ] 1.11 Add unit tests for all history edge cases.

## 2. ComposerInput integration

- [ ] 2.1 Add an `InputHistory` instance to ComposerInput or inject one from the app.
- [ ] 2.2 Bind Up to previous history item.
- [ ] 2.3 Bind Down to next history item.
- [ ] 2.4 Optionally bind Ctrl+P to previous history item.
- [ ] 2.5 Optionally bind Ctrl+N to next history item.
- [ ] 2.6 Push submitted non-empty text into history.
- [ ] 2.7 Reset history navigation after submit.
- [ ] 2.8 Reset history navigation when user types new text manually.
- [ ] 2.9 Ensure history works for slash commands.
- [ ] 2.10 Ensure history works for natural-language input.
- [ ] 2.11 Ensure history works for chat-local commands.
- [ ] 2.12 Add headless TUI tests for Up/Down behavior.

## 3. Optional persistent history

- [ ] 3.1 Decide whether implementation includes persisted history in this PR.
- [ ] 3.2 If persistence is deferred, document that history is in-session only.
- [ ] 3.3 If implemented, add bounded JSONL or warehouse-backed persistence.
- [ ] 3.4 Add config/env flag to disable persisted history.
- [ ] 3.5 Apply redaction/sensitive-pattern skip rules.
- [ ] 3.6 Do not store empty input.
- [ ] 3.7 Do not store raw secrets/tokens/cookies.
- [ ] 3.8 Add tests for persisted history if implemented.

## 4. Runtime status model

- [ ] 4.1 Add `vnalpha/src/vnalpha/tui/runtime_status.py`.
- [ ] 4.2 Define `RuntimeState` enum or equivalent constants.
- [ ] 4.3 Define `RuntimeStatus` dataclass or equivalent model.
- [ ] 4.4 Include current state, label, detail, started_at, last_error.
- [ ] 4.5 Add state transition helper.
- [ ] 4.6 Add tests for status model transitions.

## 5. Status bar widget

- [ ] 5.1 Add `vnalpha/src/vnalpha/tui/widgets/status_bar.py`.
- [ ] 5.2 Render compact one-line status.
- [ ] 5.3 Show IDLE/READY state.
- [ ] 5.4 Show command-running state.
- [ ] 5.5 Show chat-thinking state.
- [ ] 5.6 Show tool-running state.
- [ ] 5.7 Show data-ensure/sync/build/score states.
- [ ] 5.8 Show warning state.
- [ ] 5.9 Show error state.
- [ ] 5.10 Show service-unavailable state where detected.
- [ ] 5.11 Keep status bar compact and non-primary.
- [ ] 5.12 Add tests for status bar text rendering.

## 6. App/router status integration

- [ ] 6.1 Wire status bar into `VnAlphaApp` without breaking layout constraints.
- [ ] 6.2 Set `ROUTING_INPUT` when input submission starts.
- [ ] 6.3 Set `COMMAND_RUNNING` for slash command route.
- [ ] 6.4 Set `CHAT_THINKING` for natural-language route.
- [ ] 6.5 Set `TOOL_RUNNING` on tool trace running events.
- [ ] 6.6 Set data provisioning states during `/explain` and assistant data ensure flows where feasible.
- [ ] 6.7 Set `READY` after successful completion.
- [ ] 6.8 Set `WARNING` when result has warnings but no hard failure.
- [ ] 6.9 Set `ERROR` when route/render/command/chat fails.
- [ ] 6.10 Ensure status is reset or updated after cancellation.
- [ ] 6.11 Add tests for route-driven status transitions.

## 7. OutputStream visual polish

- [ ] 7.1 Standardize user message block rendering.
- [ ] 7.2 Standardize assistant message block rendering.
- [ ] 7.3 Standardize command result block rendering.
- [ ] 7.4 Standardize tool trace block rendering.
- [ ] 7.5 Standardize data readiness/provisioning block rendering if applicable.
- [ ] 7.6 Standardize warning block rendering.
- [ ] 7.7 Standardize error block rendering.
- [ ] 7.8 Use compact labels consistently.
- [ ] 7.9 Avoid excessive vertical noise.
- [ ] 7.10 Keep markup robust when text contains brackets/special characters.
- [ ] 7.11 Add tests for semantic output methods.

## 8. Footer/keybinding hints

- [ ] 8.1 Add or update compact footer hint.
- [ ] 8.2 Include `Enter submit`.
- [ ] 8.3 Include `Up/Down history`.
- [ ] 8.4 Include `Ctrl+L clear`.
- [ ] 8.5 Include `/help commands`.
- [ ] 8.6 Include `Esc cancel/clear`.
- [ ] 8.7 Keep footer compact and non-primary.
- [ ] 8.8 Add tests only for content presence, not exact styling.

## 9. Operational states for auto data provisioning

- [ ] 9.1 Show visible state when ensure-data starts.
- [ ] 9.2 Show visible state when OHLCV sync starts.
- [ ] 9.3 Show visible state when benchmark sync starts.
- [ ] 9.4 Show visible state when canonical build starts.
- [ ] 9.5 Show visible state when feature build starts.
- [ ] 9.6 Show visible state when scoring starts.
- [ ] 9.7 Show visible READY when data ensure succeeds.
- [ ] 9.8 Show visible WARNING when data ensure is partial.
- [ ] 9.9 Show visible ERROR when data ensure fails.
- [ ] 9.10 Add tests or documented adapter behavior for data provisioning states.

## 10. Observability

- [ ] 10.1 Emit `TUI_HISTORY_PUSHED` or equivalent.
- [ ] 10.2 Emit `TUI_HISTORY_PREVIOUS` or equivalent.
- [ ] 10.3 Emit `TUI_HISTORY_NEXT` or equivalent.
- [ ] 10.4 Emit `TUI_HISTORY_DRAFT_RESTORED` or equivalent.
- [ ] 10.5 Emit `TUI_STATUS_CHANGED` or equivalent.
- [ ] 10.6 Avoid logging raw full input unless redacted.
- [ ] 10.7 Log input kind and length instead of raw sensitive content where possible.
- [ ] 10.8 Add tests or mocks proving observability hooks are called.

## 11. Layout regression tests

- [ ] 11.1 Assert exactly one `ComposerInput` in default app.
- [ ] 11.2 Assert exactly one primary `OutputStream` in default app.
- [ ] 11.3 Assert exactly one Textual `Input` in default app.
- [ ] 11.4 Assert no `ContentSwitcher` in default path.
- [ ] 11.5 Assert no secondary `ChatPanel` in default path.
- [ ] 11.6 Assert no `CommandScreen` in default workflow.
- [ ] 11.7 Assert status/footer widgets, if present, are supporting widgets.

## 12. Documentation

- [ ] 12.1 Update `vnalpha/docs/tui-workspace.md`.
- [ ] 12.2 Document Up/Down history.
- [ ] 12.3 Document Ctrl+P/Ctrl+N if implemented.
- [ ] 12.4 Document status states.
- [ ] 12.5 Document data provisioning status messages.
- [ ] 12.6 Document visible clear vs persisted audit/history.
- [ ] 12.7 Document how to diagnose ERROR/SERVICE_UNAVAILABLE.

## 13. Validation

- [ ] 13.1 Run `make test-vnalpha`.
- [ ] 13.2 Run `make lint-vnalpha`.
- [ ] 13.3 Run `make verify-r4`.
- [ ] 13.4 Run `openstock-verify --ci`.
- [ ] 13.5 Add validation evidence for Up/Down history.
- [ ] 13.6 Add validation evidence for status transitions.
- [ ] 13.7 Add validation evidence that default layout constraints still pass.
