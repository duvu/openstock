# Tasks: Refactor TUI into opencode-like chat-first workspace

## 0. Governance

- [ ] 0.1 Treat this as a UX/interaction-model refactor, not a cosmetic CSS-only change.
- [ ] 0.2 Preserve existing business functionality through ChatController, CommandExecutor, logs, repair, deploy, and domain services.
- [ ] 0.3 Preserve closed-loop observability for TUI interactions.
- [ ] 0.4 Preserve redaction-by-default logging behavior.
- [ ] 0.5 Keep the system in read-only research mode.
- [ ] 0.6 Do not mark tasks complete without tests or validation evidence.

## 1. Default TUI layout

- [ ] 1.1 Refactor `VnAlphaApp.compose()` to mount `OutputStream` and `ComposerInput` as the only primary visible regions.
- [ ] 1.2 Remove `ContentSwitcher` from the default `vnalpha tui` path.
- [ ] 1.3 Remove persistent secondary `ChatPanel` from the default `vnalpha tui` path.
- [ ] 1.4 Ensure the default DOM has exactly one Textual `Input` widget.
- [ ] 1.5 Ensure the output region uses remaining terminal height.
- [ ] 1.6 Ensure the composer region has fixed/compact height.
- [ ] 1.7 Preserve app mount stability in headless tests.

## 2. OutputStream widget

- [ ] 2.1 Add `vnalpha.tui.widgets.output_stream.OutputStream`.
- [ ] 2.2 Implement `show_user_input(text)`.
- [ ] 2.3 Implement `show_assistant_message(text, style=None)`.
- [ ] 2.4 Implement `show_command_result(command, markup)`.
- [ ] 2.5 Implement `show_error(message, source=None)`.
- [ ] 2.6 Implement `show_warning(message, source=None)`.
- [ ] 2.7 Implement `show_trace_event(event)`.
- [ ] 2.8 Implement `show_table_or_markup(markup)`.
- [ ] 2.9 Implement `show_repair_bundle(path, repair_id=None)`.
- [ ] 2.10 Implement `show_deploy_status(status, details=None)`.
- [ ] 2.11 Implement `clear_visible()` for visible stream clearing only.
- [ ] 2.12 Ensure output rendering is append-only unless explicitly cleared.

## 3. ComposerInput widget

- [ ] 3.1 Add `vnalpha.tui.widgets.composer_input.ComposerInput`.
- [ ] 3.2 ComposerInput owns exactly one Textual `Input`.
- [ ] 3.3 Placeholder says `Ask or run /command ...` or equivalent.
- [ ] 3.4 Enter submits text through a `ComposerSubmitted` message.
- [ ] 3.5 Empty submissions are ignored.
- [ ] 3.6 Submitted text clears the input.
- [ ] 3.7 Esc clears input or cancels pending plan when routed by app.
- [ ] 3.8 Ctrl+L clears the visible OutputStream only.

## 4. Input router

- [ ] 4.1 Add `vnalpha.tui.input_router.TuiInputRouter` or equivalent.
- [ ] 4.2 Route empty input to no-op.
- [ ] 4.3 Route `/clear` to `OutputStream.clear_visible()`.
- [ ] 4.4 Route `/approve` and `approve` to ChatController pending plan approval.
- [ ] 4.5 Route `/cancel` and `cancel` to ChatController pending plan cancellation.
- [ ] 4.6 Route slash commands to CommandExecutor.
- [ ] 4.7 Route natural-language input to ChatController.
- [ ] 4.8 Render user input into OutputStream before execution.
- [ ] 4.9 Render command result into OutputStream.
- [ ] 4.10 Render assistant callbacks into OutputStream.
- [ ] 4.11 Render tool trace callbacks into OutputStream.
- [ ] 4.12 Render errors/warnings into OutputStream.

## 5. Command execution integration

- [ ] 5.1 Reuse `CommandExecutor` for slash commands.
- [ ] 5.2 Reuse existing textual command result renderer where possible.
- [ ] 5.3 Do not depend on `CommandScreen` for default command execution.
- [ ] 5.4 Support existing research commands such as `/help`, `/scan`, `/explain`, `/filter`, `/history` if available.
- [ ] 5.5 Support logs command path from composer.
- [ ] 5.6 Support repair command path from composer.
- [ ] 5.7 Support deploy command path from composer.
- [ ] 5.8 Command failures render inline and log errors.

## 6. ChatController integration

- [ ] 6.1 Reuse ChatController for natural-language turns.
- [ ] 6.2 Bootstrap chat session as needed.
- [ ] 6.3 Close warehouse connections opened during session bootstrap.
- [ ] 6.4 Assistant messages render into OutputStream.
- [ ] 6.5 Refusals render into OutputStream.
- [ ] 6.6 Plan preview renders into OutputStream.
- [ ] 6.7 Plan approval/cancellation renders into OutputStream.
- [ ] 6.8 Chat runtime errors render inline and are captured by observability.

## 7. Closed-loop observability

- [ ] 7.1 Emit `TUI_INPUT_SUBMITTED` for every non-empty submitted input.
- [ ] 7.2 Emit `TUI_COMMAND_ROUTED` for slash commands.
- [ ] 7.3 Emit `TUI_CHAT_ROUTED` for natural-language input.
- [ ] 7.4 Emit `TUI_RENDER_ERROR` or equivalent on render failures.
- [ ] 7.5 Ensure each TUI submission has a non-empty correlation ID.
- [ ] 7.6 Ensure slash commands preserve command lifecycle events.
- [ ] 7.7 Ensure natural-language turns preserve ChatController events.
- [ ] 7.8 Ensure tool trace events still persist and render inline.
- [ ] 7.9 Ensure `/clear` does not delete audit logs or persisted chat history.

## 8. Legacy dashboard handling

- [ ] 8.1 Remove legacy screen switching from default TUI workflow.
- [ ] 8.2 Do not mount `HomeScreen`, `WatchlistScreen`, `CommandScreen`, `AssistantScreen`, `RejectedScreen`, `QualityScreen`, `OutcomeScreen`, or `LogScreen` by default.
- [ ] 8.3 Keep legacy modules importable unless deletion is explicitly justified.
- [ ] 8.4 Update or retire tests that assume screen switching is the primary workflow.
- [ ] 8.5 Document legacy status in TUI docs.

## 9. Tests

- [ ] 9.1 Add test: app mounts.
- [ ] 9.2 Add test: exactly one `ComposerInput` exists.
- [ ] 9.3 Add test: exactly one `OutputStream` exists.
- [ ] 9.4 Add test: exactly one Textual `Input` exists.
- [ ] 9.5 Add test: no `ContentSwitcher` exists in default DOM.
- [ ] 9.6 Add test: no `ChatPanel` exists in default DOM.
- [ ] 9.7 Add test: no `CommandInput` exists in default DOM.
- [ ] 9.8 Add test: no `CommandResultPanel` exists in default DOM.
- [ ] 9.9 Add test: natural-language input routes to ChatController.
- [ ] 9.10 Add test: slash command input routes to CommandExecutor.
- [ ] 9.11 Add test: command result renders into OutputStream.
- [ ] 9.12 Add test: assistant answer renders into OutputStream.
- [ ] 9.13 Add test: tool trace renders into OutputStream.
- [ ] 9.14 Add test: render error calls capture_exception or equivalent.
- [ ] 9.15 Add test: `/clear` clears visible output only.
- [ ] 9.16 Add test: TUI input emits observability audit event.

## 10. Documentation and validation

- [ ] 10.1 Add or update TUI documentation with opencode-like model.
- [ ] 10.2 Document single input routing rules.
- [ ] 10.3 Document slash command examples.
- [ ] 10.4 Document logs/repair/deploy examples from composer.
- [ ] 10.5 Document legacy dashboard status.
- [ ] 10.6 Run `make test-vnalpha`.
- [ ] 10.7 Run `make lint-vnalpha`.
- [ ] 10.8 Run `make verify-r4`.
- [ ] 10.9 Run `openstock-verify --ci`.
- [ ] 10.10 Add validation evidence before archiving the OpenSpec change.
