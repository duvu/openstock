# Tasks: Responsive TODO side panel

## 0. Governance and consistency

- [x] 0.1 Preserve opencode-like primary workflow.
- [x] 0.2 Keep exactly one primary `OutputStream`.
- [x] 0.3 Keep exactly one primary `ComposerInput`.
- [x] 0.4 Keep exactly one Textual `Input` in default TUI.
- [x] 0.5 Do not reintroduce `ContentSwitcher` in default path.
- [x] 0.6 Do not reintroduce secondary `ChatPanel`.
- [x] 0.7 Do not add input/edit controls inside TodoPanel.
- [ ] 0.8 Keep TODO edits routed through ComposerInput commands.
- [x] 0.9 Desktop TODO panel must be secondary side rail, not primary workspace.
- [x] 0.10 Narrow/tmux/phone layout must remain usable.
- [x] 0.11 Do not mark complete without wide/narrow layout tests.

## 1. Responsive layout policy

- [x] 1.1 Add `vnalpha/src/vnalpha/tui/responsive_layout.py`.
- [x] 1.2 Add `ResponsiveLayoutPolicy`.
- [x] 1.3 Add `ResponsiveLayoutController`.
- [x] 1.4 Default TODO visible min width to 120 columns.
- [x] 1.5 Default TODO min width to 28 columns.
- [x] 1.6 Default TODO preferred width to 32 columns.
- [x] 1.7 Default TODO max width to 40 columns.
- [x] 1.8 Hard-hide TODO panel below min width.
- [x] 1.9 Respect manual preference only when terminal is wide enough.
- [x] 1.10 Add unit tests for width policy.

## 2. TODO model and source interface

- [x] 2.1 Add `vnalpha/src/vnalpha/tui/todo_source.py`.
- [x] 2.2 Define `TodoItem` model.
- [x] 2.3 Define `TodoSource` protocol/interface.
- [x] 2.4 Implement `FallbackTodoSource`.
- [x] 2.5 Implement `WorkspaceTodoSource` adapter.
- [x] 2.6 Implement `CompositeTodoSource`.
- [x] 2.7 Deduplicate items by stable id or title/source.
- [x] 2.8 Add tests for each source.

## 3. TodoPanel widget

- [x] 3.1 Add `vnalpha/src/vnalpha/tui/widgets/todo_panel.py`.
- [x] 3.2 Render panel title.
- [x] 3.3 Render grouped TODO items.
- [x] 3.4 Render active items.
- [x] 3.5 Render blocked items.
- [x] 3.6 Render next/open items.
- [ ] 3.7 Render recently done items if available.
- [x] 3.8 Render empty state.
- [x] 3.9 Render compact priority/status badges.
- [x] 3.10 Expose `refresh()` method.
- [x] 3.11 Do not mount any Textual `Input` inside TodoPanel.
- [x] 3.12 Do not take focus by default.
- [x] 3.13 Add widget tests for empty and populated states.

## 4. App layout integration

- [x] 4.1 Refactor `VnAlphaApp` layout to support `MainBody` horizontal container on wide screens.
- [x] 4.2 Mount `OutputStream` in the main output column.
- [x] 4.3 Mount `TodoPanel` as right side rail only when policy allows.
- [x] 4.4 Preserve `ComposerInput` below output/main body.
- [x] 4.5 Preserve status/header/footer support regions if present.
- [x] 4.6 Keep ComposerInput focus after mount.
- [x] 4.7 Add layout regression tests.

## 5. Resize behavior

- [x] 5.1 Detect terminal resize events.
- [x] 5.2 Recompute TODO visibility on resize.
- [x] 5.3 Hide/collapse TODO panel when width becomes narrow.
- [x] 5.4 Restore TODO panel when width becomes wide and preference allows.
- [x] 5.5 Keep OutputStream and ComposerInput usable after resize.
- [x] 5.6 Add resize tests.

## 6. Toggle behavior

- [x] 6.1 Add action `toggle_todo_panel` or equivalent.
- [x] 6.2 Bind `Ctrl+T` if not conflicting.
- [x] 6.3 Toggle TODO panel on wide terminals.
- [x] 6.4 Do not allow toggle to force panel visible on narrow terminals.
- [x] 6.5 Keep ComposerInput focus after toggle.
- [ ] 6.6 Persist manual preference if existing config/workspace context supports it.
- [x] 6.7 Add toggle tests.

## 7. TODO commands

- [x] 7.1 Decide whether `/todo` commands are implemented in this PR or mapped to `/context task`.
- Deferred in this change: the repo does not currently have a workspace-task mutation command surface (`/todo` or `/context task`), so the panel remains intentionally read-only.
- [ ] 7.2 Add `/todo list` if implemented.
- [ ] 7.3 Add `/todo add <text>` if implemented.
- [ ] 7.4 Add `/todo done <id>` if implemented.
- [ ] 7.5 Add `/todo block <id>` if implemented.
- [ ] 7.6 Add `/todo clear-done` if implemented.
- [ ] 7.7 Refresh TodoPanel after TODO-changing commands.
- [ ] 7.8 Add command tests if commands are implemented.

## 8. Workspace context integration

- [x] 8.1 Map workspace tasks to TodoItem where workspace_context exists.
- [x] 8.2 Degrade gracefully if workspace_context is not available.
- [ ] 8.3 Include system-generated follow-ups where appropriate.
- [x] 8.4 Include stale data or blocked data readiness warnings where appropriate.
- [x] 8.5 Do not duplicate full workspace context.
- [x] 8.6 Add integration tests with fake workspace tasks.

## 9. Visual consistency

- [x] 9.1 Reuse existing color/status vocabulary where possible.
- [x] 9.2 Use consistent border and padding style with OutputStream/status bar.
- [x] 9.3 Use compact labels.
- [x] 9.4 Avoid excessive vertical noise.
- [x] 9.5 Ensure panel looks coherent with desktop TUI.
- [x] 9.6 Ensure hidden/collapsed state does not leave awkward gaps.
- [x] 9.7 Add semantic tests rather than exact color tests.

## 10. Footer/status hints

- [x] 10.1 Add footer/status hint for TODO toggle.
- [x] 10.2 Show `Ctrl+T TODOs` or equivalent on wide terminals.
- [x] 10.3 Show `TODOs hidden: narrow terminal` or equivalent on narrow terminals when useful.
- [x] 10.4 Document in TUI docs.

## 11. Observability

- [x] 11.1 Emit `TUI_TODO_PANEL_VISIBLE`.
- [x] 11.2 Emit `TUI_TODO_PANEL_HIDDEN`.
- [x] 11.3 Emit `TUI_TODO_PANEL_TOGGLED`.
- [x] 11.4 Emit `TUI_TODO_PANEL_REFRESHED`.
- [ ] 11.5 Emit TODO item add/update events if commands are implemented.
- [x] 11.6 Avoid raw full task text in audit events unless redacted.
- [x] 11.7 Add observability tests or mocks.

## 12. Layout tests

- [x] 12.1 Width 140: TodoPanel visible.
- [x] 12.2 Width 120: TodoPanel visible.
- [x] 12.3 Width 119: TodoPanel hidden.
- [x] 12.4 Width 80: TodoPanel hidden.
- [x] 12.5 Resize 140 -> 80 hides panel.
- [x] 12.6 Resize 80 -> 140 restores panel unless preference disabled.
- [x] 12.7 Manual toggle hides on wide.
- [x] 12.8 Manual toggle cannot force visible on narrow.
- [x] 12.9 Default DOM has exactly one Textual `Input`.
- [x] 12.10 TodoPanel has no Textual `Input`.

## 13. Documentation

- [x] 13.1 Update `vnalpha/docs/tui-workspace.md`.
- [x] 13.2 Document desktop layout.
- [x] 13.3 Document narrow/tmux/phone layout.
- [x] 13.4 Document breakpoint policy.
- [x] 13.5 Document toggle key.
- [x] 13.6 Document TODO source behavior.
- [x] 13.7 Document `/todo` or `/context task` commands.
- [x] 13.8 Document consistency constraints.

## 14. Validation

- [ ] 14.1 Run `make test-vnalpha`.
- [ ] 14.2 Run `make lint-vnalpha`.
- [x] 14.3 Run `make verify-r4`.
- [x] 14.4 Run `openstock-verify --ci`.
- [x] 14.5 Add validation evidence for desktop-width TUI.
- [x] 14.6 Add validation evidence for narrow/tmux-like TUI.
- [x] 14.7 Add validation evidence for layout consistency regression tests.
- Validation note: `make test-vnalpha` is still blocked by the pre-existing `tests/test_tui_command.py::TestCommandWidgetsStatic::test_textual_renderer_returns_string` failure, and `make lint-vnalpha` currently fails on unrelated import-order files under `workspace_context`.
