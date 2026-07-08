# Tasks: Responsive TODO side panel

## 0. Governance and consistency

- [ ] 0.1 Preserve opencode-like primary workflow.
- [ ] 0.2 Keep exactly one primary `OutputStream`.
- [ ] 0.3 Keep exactly one primary `ComposerInput`.
- [ ] 0.4 Keep exactly one Textual `Input` in default TUI.
- [ ] 0.5 Do not reintroduce `ContentSwitcher` in default path.
- [ ] 0.6 Do not reintroduce secondary `ChatPanel`.
- [ ] 0.7 Do not add input/edit controls inside TodoPanel.
- [ ] 0.8 Keep TODO edits routed through ComposerInput commands.
- [ ] 0.9 Desktop TODO panel must be secondary side rail, not primary workspace.
- [ ] 0.10 Narrow/tmux/phone layout must remain usable.
- [ ] 0.11 Do not mark complete without wide/narrow layout tests.

## 1. Responsive layout policy

- [ ] 1.1 Add `vnalpha/src/vnalpha/tui/responsive_layout.py`.
- [ ] 1.2 Add `ResponsiveLayoutPolicy`.
- [ ] 1.3 Add `ResponsiveLayoutController`.
- [ ] 1.4 Default TODO visible min width to 120 columns.
- [ ] 1.5 Default TODO min width to 28 columns.
- [ ] 1.6 Default TODO preferred width to 32 columns.
- [ ] 1.7 Default TODO max width to 40 columns.
- [ ] 1.8 Hard-hide TODO panel below min width.
- [ ] 1.9 Respect manual preference only when terminal is wide enough.
- [ ] 1.10 Add unit tests for width policy.

## 2. TODO model and source interface

- [ ] 2.1 Add `vnalpha/src/vnalpha/tui/todo_source.py`.
- [ ] 2.2 Define `TodoItem` model.
- [ ] 2.3 Define `TodoSource` protocol/interface.
- [ ] 2.4 Implement `FallbackTodoSource`.
- [ ] 2.5 Implement `WorkspaceTodoSource` adapter.
- [ ] 2.6 Implement `CompositeTodoSource`.
- [ ] 2.7 Deduplicate items by stable id or title/source.
- [ ] 2.8 Add tests for each source.

## 3. TodoPanel widget

- [ ] 3.1 Add `vnalpha/src/vnalpha/tui/widgets/todo_panel.py`.
- [ ] 3.2 Render panel title.
- [ ] 3.3 Render grouped TODO items.
- [ ] 3.4 Render active items.
- [ ] 3.5 Render blocked items.
- [ ] 3.6 Render next/open items.
- [ ] 3.7 Render recently done items if available.
- [ ] 3.8 Render empty state.
- [ ] 3.9 Render compact priority/status badges.
- [ ] 3.10 Expose `refresh()` method.
- [ ] 3.11 Do not mount any Textual `Input` inside TodoPanel.
- [ ] 3.12 Do not take focus by default.
- [ ] 3.13 Add widget tests for empty and populated states.

## 4. App layout integration

- [ ] 4.1 Refactor `VnAlphaApp` layout to support `MainBody` horizontal container on wide screens.
- [ ] 4.2 Mount `OutputStream` in the main output column.
- [ ] 4.3 Mount `TodoPanel` as right side rail only when policy allows.
- [ ] 4.4 Preserve `ComposerInput` below output/main body.
- [ ] 4.5 Preserve status/header/footer support regions if present.
- [ ] 4.6 Keep ComposerInput focus after mount.
- [ ] 4.7 Add layout regression tests.

## 5. Resize behavior

- [ ] 5.1 Detect terminal resize events.
- [ ] 5.2 Recompute TODO visibility on resize.
- [ ] 5.3 Hide/collapse TODO panel when width becomes narrow.
- [ ] 5.4 Restore TODO panel when width becomes wide and preference allows.
- [ ] 5.5 Keep OutputStream and ComposerInput usable after resize.
- [ ] 5.6 Add resize tests.

## 6. Toggle behavior

- [ ] 6.1 Add action `toggle_todo_panel` or equivalent.
- [ ] 6.2 Bind `Ctrl+T` if not conflicting.
- [ ] 6.3 Toggle TODO panel on wide terminals.
- [ ] 6.4 Do not allow toggle to force panel visible on narrow terminals.
- [ ] 6.5 Keep ComposerInput focus after toggle.
- [ ] 6.6 Persist manual preference if existing config/workspace context supports it.
- [ ] 6.7 Add toggle tests.

## 7. TODO commands

- [ ] 7.1 Decide whether `/todo` commands are implemented in this PR or mapped to `/context task`.
- [ ] 7.2 Add `/todo list` if implemented.
- [ ] 7.3 Add `/todo add <text>` if implemented.
- [ ] 7.4 Add `/todo done <id>` if implemented.
- [ ] 7.5 Add `/todo block <id>` if implemented.
- [ ] 7.6 Add `/todo clear-done` if implemented.
- [ ] 7.7 Refresh TodoPanel after TODO-changing commands.
- [ ] 7.8 Add command tests if commands are implemented.

## 8. Workspace context integration

- [ ] 8.1 Map workspace tasks to TodoItem where workspace_context exists.
- [ ] 8.2 Degrade gracefully if workspace_context is not available.
- [ ] 8.3 Include system-generated follow-ups where appropriate.
- [ ] 8.4 Include stale data or blocked data readiness warnings where appropriate.
- [ ] 8.5 Do not duplicate full workspace context.
- [ ] 8.6 Add integration tests with fake workspace tasks.

## 9. Visual consistency

- [ ] 9.1 Reuse existing color/status vocabulary where possible.
- [ ] 9.2 Use consistent border and padding style with OutputStream/status bar.
- [ ] 9.3 Use compact labels.
- [ ] 9.4 Avoid excessive vertical noise.
- [ ] 9.5 Ensure panel looks coherent with desktop TUI.
- [ ] 9.6 Ensure hidden/collapsed state does not leave awkward gaps.
- [ ] 9.7 Add semantic tests rather than exact color tests.

## 10. Footer/status hints

- [ ] 10.1 Add footer/status hint for TODO toggle.
- [ ] 10.2 Show `Ctrl+T TODOs` or equivalent on wide terminals.
- [ ] 10.3 Show `TODOs hidden: narrow terminal` or equivalent on narrow terminals when useful.
- [ ] 10.4 Document in TUI docs.

## 11. Observability

- [ ] 11.1 Emit `TUI_TODO_PANEL_VISIBLE`.
- [ ] 11.2 Emit `TUI_TODO_PANEL_HIDDEN`.
- [ ] 11.3 Emit `TUI_TODO_PANEL_TOGGLED`.
- [ ] 11.4 Emit `TUI_TODO_PANEL_REFRESHED`.
- [ ] 11.5 Emit TODO item add/update events if commands are implemented.
- [ ] 11.6 Avoid raw full task text in audit events unless redacted.
- [ ] 11.7 Add observability tests or mocks.

## 12. Layout tests

- [ ] 12.1 Width 140: TodoPanel visible.
- [ ] 12.2 Width 120: TodoPanel visible.
- [ ] 12.3 Width 119: TodoPanel hidden.
- [ ] 12.4 Width 80: TodoPanel hidden.
- [ ] 12.5 Resize 140 -> 80 hides panel.
- [ ] 12.6 Resize 80 -> 140 restores panel unless preference disabled.
- [ ] 12.7 Manual toggle hides on wide.
- [ ] 12.8 Manual toggle cannot force visible on narrow.
- [ ] 12.9 Default DOM has exactly one Textual `Input`.
- [ ] 12.10 TodoPanel has no Textual `Input`.

## 13. Documentation

- [ ] 13.1 Update `vnalpha/docs/tui-workspace.md`.
- [ ] 13.2 Document desktop layout.
- [ ] 13.3 Document narrow/tmux/phone layout.
- [ ] 13.4 Document breakpoint policy.
- [ ] 13.5 Document toggle key.
- [ ] 13.6 Document TODO source behavior.
- [ ] 13.7 Document `/todo` or `/context task` commands.
- [ ] 13.8 Document consistency constraints.

## 14. Validation

- [ ] 14.1 Run `make test-vnalpha`.
- [ ] 14.2 Run `make lint-vnalpha`.
- [ ] 14.3 Run `make verify-r4`.
- [ ] 14.4 Run `openstock-verify --ci`.
- [ ] 14.5 Add validation evidence for desktop-width TUI.
- [ ] 14.6 Add validation evidence for narrow/tmux-like TUI.
- [ ] 14.7 Add validation evidence for layout consistency regression tests.
