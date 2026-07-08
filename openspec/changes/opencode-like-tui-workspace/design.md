# Design: Opencode-like chat-first TUI workspace

## Design objective

Replace the default multi-screen TUI with a terminal-agent workspace:

```text
OutputStream
ComposerInput
```

The TUI should feel like a single ongoing conversation where commands, tool calls, logs, repair actions, deploy actions, and assistant answers all render into one stream.

## Design principles

1. **One input**: the default TUI must expose one composer only.
2. **One output stream**: all results render into one scrollable stream.
3. **Chat-first**: natural language is the primary interaction mode.
4. **Slash-command compatible**: slash commands remain first-class.
5. **Inline tool visibility**: tool trace and command status render inline.
6. **No dashboard switching in default path**: screen-switching is not the primary workflow.
7. **Reuse existing logic**: use ChatController and CommandExecutor.
8. **Observability preserved**: TUI interactions remain part of the closed-loop logging system.
9. **Legacy-safe**: old screens may stay importable but are not mounted by default.

## Proposed files

Create:

```text
vnalpha/src/vnalpha/tui/widgets/output_stream.py
vnalpha/src/vnalpha/tui/widgets/composer_input.py
vnalpha/src/vnalpha/tui/input_router.py
```

Refactor:

```text
vnalpha/src/vnalpha/tui/app.py
vnalpha/tests/test_tui_pilot.py or replacement TUI tests
```

Possibly deprecate default usage of:

```text
vnalpha/src/vnalpha/tui/widgets/chat_panel.py
vnalpha/src/vnalpha/tui/widgets/command_input.py
vnalpha/src/vnalpha/tui/widgets/command_result.py
vnalpha/src/vnalpha/tui/screens/command.py
```

## Layout

### App compose

Default `VnAlphaApp.compose()` should be conceptually:

```python
class VnAlphaApp(App):
    def compose(self):
        yield OutputStream(id="output-stream")
        yield ComposerInput(id="composer-input")
```

CSS should allocate most height to output and a fixed height to composer:

```css
OutputStream {
    height: 1fr;
}

ComposerInput {
    height: 3;
}
```

No `ContentSwitcher` should be mounted in the default path.

No separate `ChatPanel` should be mounted below a main workspace.

## OutputStream

`OutputStream` should be RichLog-based or equivalent.

Suggested public methods:

```python
show_user_input(text: str) -> None
show_assistant_message(text: str, style: str | None = None) -> None
show_command_result(command: str, markup: str) -> None
show_error(message: str, source: str | None = None) -> None
show_warning(message: str, source: str | None = None) -> None
show_trace_event(event) -> None
show_table_or_markup(markup: str) -> None
show_repair_bundle(path: str, repair_id: str | None = None) -> None
show_deploy_status(status: str, details: str | None = None) -> None
clear_visible() -> None
```

Rendering should be append-only by default. `/clear` clears visible output only and must not delete audit logs or persisted chat history.

## ComposerInput

`ComposerInput` should own exactly one Textual `Input` widget.

Suggested behavior:

```text
Enter submits text
Esc cancels pending plan if one exists, otherwise clears input
Ctrl+L clears OutputStream
```

Suggested message:

```python
class ComposerSubmitted(Message):
    text: str
```

Placeholder:

```text
Ask or run /command ...
```

## Input routing

Create `TuiInputRouter` or equivalent orchestration adapter.

Routing rules:

```text
empty input              -> no-op
/clear                   -> output_stream.clear_visible()
/approve or approve      -> ChatController.approve_pending_plan()
/cancel or cancel        -> ChatController.cancel_pending_plan()
starts with /            -> CommandExecutor.execute(text)
otherwise                -> ChatController.handle_turn(text)
```

## Command execution path

Slash command flow:

```text
ComposerInput submitted
OutputStream shows user input
TuiInputRouter calls CommandExecutor
CommandExecutor returns result
result_to_markup() converts result
OutputStream.show_command_result()
observability writes command lifecycle events
```

Command execution should not require `CommandScreen`.

## Natural-language path

Natural-language flow:

```text
ComposerInput submitted
OutputStream shows user input
TuiInputRouter calls ChatController.handle_turn()
ChatController callbacks write messages to OutputStream
Tool trace callbacks render into OutputStream
errors render into OutputStream and are captured by observability
```

## Logs, repair, and deploy path

Initially these can be supported through CommandExecutor if it knows how to dispatch them, or through a small bridge in `TuiInputRouter`.

Required user-facing examples:

```text
/logs errors --latest
/logs summarize --latest
/repair prepare --latest
/repair status <repair-id>
/deploy verify <candidate>
/deploy promote <candidate> --deployment-id <id>
/deploy rollback <deployment-id>
```

If these are not already CommandExecutor commands, add bridge handlers that call the existing CLI/service functions and render into OutputStream.

## Observability

TUI input handling must emit:

```text
TUI_INPUT_SUBMITTED
TUI_COMMAND_ROUTED
TUI_CHAT_ROUTED
TUI_RENDER_ERROR
```

Slash commands should preserve command lifecycle events.

Natural-language turns should preserve ChatController events.

Every submission should create or reuse a correlation ID.

## Legacy screens

The implementation may keep these modules in the repository:

```text
HomeScreen
WatchlistScreen
CommandScreen
AssistantScreen
RejectedScreen
QualityScreen
OutcomeScreen
LogScreen
```

But the default `vnalpha tui` should not mount them. If legacy dashboard remains needed, add an explicit future option such as:

```text
vnalpha tui --legacy-dashboard
```

The OpenSpec does not require implementing that flag in the first PR.

## Test strategy

Add tests that assert:

```text
app mounts
exactly one ComposerInput exists
exactly one OutputStream exists
exactly one Textual Input exists
ContentSwitcher does not exist in default DOM
ChatPanel does not exist in default DOM
CommandInput does not exist in default DOM
CommandResultPanel does not exist in default DOM
plain text routes to ChatController
slash command routes to CommandExecutor
command output is rendered into OutputStream
chat output is rendered into OutputStream
tool trace is rendered into OutputStream
render errors are captured by observability
```

Retire or update tests that assert primary screen switching.

## Validation

Implementation PR should run:

```text
make test-vnalpha
make lint-vnalpha
make verify-r4
openstock-verify --ci
```

If old TUI pilot tests are intentionally replaced, validation must state which tests were retired and why.
