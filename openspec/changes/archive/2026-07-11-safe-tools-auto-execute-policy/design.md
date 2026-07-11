# Design: Safe Tools Auto-Execute Policy and TUI Command Lifecycle

## 1. Current Problem

The current implementation mixes several concepts:

- `SAFE_READ_ONLY_TOOLS` in chat mode logic.
- planner `TOOL_ALLOWLIST`.
- executor `ASSISTANT_TOOL_ALLOWLIST`.
- tool permissions in `vnalpha.tools.setup`.
- deterministic deny lists in chat safety.

These lists do not encode one consistent product policy. The desired behavior is simpler:

1. All trusted tools in `SAFE_TOOLS` execute automatically.
2. Tools outside `SAFE_TOOLS` are refused.
3. Broker/order/account/portfolio/margin/trading execution is always hard-denied.
4. TUI command execution must remain observable and closed-loop traceable.

## 2. New Policy Model

Add a new module:

```text
vnalpha/src/vnalpha/assistant/tool_policy.py
```

Recommended API:

```python
SAFE_TOOLS: frozenset[str]
FORBIDDEN_TOOL_PREFIXES: frozenset[str]
FORBIDDEN_TOOL_NAMES: frozenset[str]

def is_forbidden_tool(tool_name: str) -> bool: ...
def is_safe_tool(tool_name: str) -> bool: ...
def assert_safe_tool(tool_name: str) -> None: ...
def is_safe_plan(plan: AssistantPlan) -> bool: ...
def unsafe_tools_in_plan(plan: AssistantPlan) -> list[str]: ...
```

Initial `SAFE_TOOLS` should include all currently trusted assistant tools:

```python
SAFE_TOOLS = frozenset({
    "watchlist.scan",
    "watchlist.filter",
    "candidate.compare",
    "candidate.explain",
    "quality.get_status",
    "quality.get_many_status",
    "lineage.get_symbol_lineage",
    "history.list_sessions",
    "note.create",
    "data.fetch",
})
```

If operational commands become tool-backed later, they may be added explicitly:

```python
"logs.errors",
"logs.summarize",
"repair.prepare",
"repair.status",
"deploy.verify",
"deploy.promote",
"deploy.rollback",
```

They must remain internal closed-loop operations, not trading execution.

## 3. Forbidden Boundary

Hard-deny names and prefixes should include at least:

```python
FORBIDDEN_TOOL_PREFIXES = frozenset({
    "broker",
    "order",
    "allocation",
    "account",
    "trading",
    "margin",
    "transfer",
    "portfolio",
})

FORBIDDEN_TOOL_NAMES = frozenset({
    "place_order",
    "cancel_order",
    "modify_order",
    "submit_order",
    "execute_order",
    "get_holdings",
    "rebalance",
    "rebalance_holdings",
    "allocate",
    "allocate_capital",
    "get_account",
    "get_account_balance",
    "transfer_funds",
    "withdraw",
    "deposit",
    "connect_broker",
    "disconnect_broker",
    "authenticate_broker",
    "auto_execute",
    "schedule_trade",
    "automated_execution",
})
```

A forbidden tool is rejected even if a future developer accidentally adds it to another registry.

## 4. Planner Integration

Replace local planner allowlist validation with `SAFE_TOOLS`.

Current pattern:

```python
TOOL_ALLOWLIST = frozenset({...})
if step.tool_name not in TOOL_ALLOWLIST:
    raise PlanValidationError(...)
```

Target pattern:

```python
from vnalpha.assistant.tool_policy import is_safe_tool

if not is_safe_tool(step.tool_name):
    raise PlanValidationError(...)
```

Planner must not maintain its own independent tool allowlist.

## 5. Executor Integration

Replace executor `ASSISTANT_TOOL_ALLOWLIST` with `SAFE_TOOLS` policy.

Target behavior:

```python
from vnalpha.assistant.tool_policy import assert_safe_tool

for step in plan.steps:
    assert_safe_tool(step.tool_name)
    execute(step)
```

Executor is the last line of defense. Even if a bad plan is constructed, executor must refuse unsafe tools.

## 6. Chat Mode Integration

Current naming `AUTO_EXECUTE_SAFE_READ_ONLY` is misleading. There are two acceptable implementation paths.

### Preferred: rename mode

```python
class ExecutionMode(str, Enum):
    AUTO_EXECUTE_SAFE_TOOLS = "auto"
    PLAN_ONLY = "plan_only"
```

### Low-churn: keep enum name but change semantics

Keep `AUTO_EXECUTE_SAFE_READ_ONLY = "auto"`, but deprecate the phrase "read-only" in docs and helper names.

In both cases:

```python
if execution_mode == PLAN_ONLY:
    render_plan_preview()
    return

if not is_safe_plan(plan):
    refuse_with_unsafe_tool_list()
    return

execute_plan_automatically()
```

No approval gate is required for `note.create` or `data.fetch` when they are present in `SAFE_TOOLS`.

## 7. TUI Command Routing

TUI routing should distinguish command classes before falling through to `CommandExecutor`:

```text
/clear, /approve, /cancel, /new, /context, /plan, /trace, /help-local
    -> chat/TUI local route
/logs ...
/repair ...
/deploy ...
    -> operational route
/research slash command
    -> CommandExecutor
natural language
    -> ChatController
```

At minimum, implement explicit operational bridge for:

```text
/logs errors --latest
/logs summarize --latest
/repair prepare --latest
/repair status <repair-id>
/deploy verify <candidate>
/deploy promote <candidate> --deployment-id <id>
/deploy rollback <deployment-id>
```

Unsupported operational subcommands must render a clear inline unsupported message rather than falling through to unknown research command.

## 8. TUI Command Lifecycle

Every TUI slash/operational command must be wrapped with `command_lifecycle()`.

Recommended shape:

```python
def _run_with_lifecycle(raw: str, fn: Callable[[], Any]) -> Any:
    with command_lifecycle("tui command", args=raw, mode="redacted"):
        return fn()
```

Apply to:

- research slash commands routed to `CommandExecutor`
- operational commands routed to logs/repair/deploy handlers
- any future tool-backed TUI command path

Expected events:

```text
COMMAND_STARTED
COMMAND_SUCCEEDED
COMMAND_FAILED
```

A non-empty correlation ID is mandatory.

## 9. TUI Resource Lifecycle

`TuiInputRouter` should own the command connection lifecycle explicitly:

```python
self._command_conn = None

# setup
conn = get_connection()
run_migrations(conn=conn)
self._command_conn = conn
self._command_executor = CommandExecutor(conn, surface="tui", default_date=...)

# close
if self._command_conn is not None:
    self._command_conn.close()
    self._command_conn = None
```

`VnAlphaApp.on_unmount()` should call `router.close()`.

## 10. Textual Thread-Safety

`ChatController.handle_turn()` runs in `asyncio.to_thread()`. Therefore callbacks passed into `ChatController` must not update Textual widgets directly from that worker thread.

Introduce a dispatcher such as:

```python
class TuiUiDispatcher:
    def __init__(self, app, output_stream, status_bar): ...
    def show_assistant_message(self, text, style=None):
        app.call_from_thread(output_stream.show_assistant_message, text, style)
    def show_trace_event(self, event):
        app.call_from_thread(output_stream.show_trace_event, event)
```

Alternative: post custom Textual messages and handle them on the app loop.

## 11. Documentation and Tests

Update docs to reflect:

- auto-execute applies to all `SAFE_TOOLS`, not read-only-only tools
- OpenStock remains research-only and does not support broker/order/account/portfolio/margin/trading execution
- `/logs`, `/repair`, `/deploy` only documented when implemented or explicitly marked unsupported/preview
- remove or implement `vnalpha tui --smoke`; do not keep weak tests that pass without verifying the flag

## 12. Non-Goals

Do not add:

- broker connectors
- order APIs
- portfolio operations
- margin operations
- account access
- trading execution
- hidden/non-redacted logging
