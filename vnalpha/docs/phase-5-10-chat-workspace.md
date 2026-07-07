# Phase 5.10 — OpenCode-Style Research Chat Workspace

> **Section 12** of the vnalpha TUI developer guide.

---

## 12.1 Chat Workspace Behavior

### Overview

The vnalpha TUI uses a persistent split-pane layout. The main workspace occupies the top portion of the screen (screens for Watchlist, Home, Commands, Assistant, Rejected, Quality, and Outcomes). The `ChatPanel` widget sits below it and remains visible across all screens.

When `VnAlphaApp` starts, it mounts the `ChatPanel` at startup and pushes `WatchlistScreen` as the default screen. The chat panel's position and visibility are independent of whichever main screen is active.

### ChatController

`ChatController` owns all chat orchestration. The `ChatPanel` widget delegates input handling to it. Each `ChatController` instance holds:

- the connection factory for the DuckDB warehouse
- a `target_date` for research context
- the `surface` string (always `"tui-chat"`)
- an `on_message` callback that the panel uses to render lines
- an optional `on_trace` callback for tool-trace events
- the active `chat_session_id`
- the current `ExecutionMode`
- a `_pending_plan` slot for the plan-approval flow

### Input classification

Every turn is classified before dispatch. `classify_input()` inspects the raw string:

1. If it starts with `/` and the first word is in `CHAT_LOCAL_COMMANDS` (`new`, `clear`, `context`, `plan`, `trace`, `help`), it's a **chat-local** command.
2. If it starts with `/` but the first word is not in that set, it's a **slash command** routed to `CommandExecutor`.
3. Everything else is **natural language** sent to the assistant.

### Natural language flow

When the input is natural language, the controller walks through a staged pipeline and emits live status lines to the chat panel at each step:

```
CLASSIFYING  →  PLANNING  →  TOOL_START  →  TOOL_SUCCESS / TOOL_FAILED  →  SYNTHESIZING  →  FINAL
```

The corresponding `AssistantStage` enum values with their display text are:

| Stage | Display text |
|---|---|
| `CLASSIFYING` | `⋯ classifying...` |
| `PLANNING` | `⋯ planning...` |
| `TOOL_START` | `⟳ <tool_name> running...` |
| `TOOL_SUCCESS` | `✓ <tool_name> success <N>ms` |
| `TOOL_FAILED` | `✗ <tool_name> failed <N>ms` |
| `SYNTHESIZING` | `⋯ synthesizing...` |
| `FINAL` | *(the assistant's answer text)* |

Internally, `handle_natural_language()` calls `_run_ask()` which constructs an `AssistantApp` connected to the warehouse and calls `app.ask()`. The behavior after that depends on the active `ExecutionMode` (see Section 12.4).

### Slash command flow

Slash commands (e.g. `/scan`, `/filter`, `/explain`) are routed to `CommandExecutor` with `surface='tui-chat'`. The executor runs migrations, resolves the registry, executes the command, and the result is rendered back to the chat panel. Errors are persisted to `chat_message` as `role='system'`.

Available research slash commands:

| Command | Purpose |
|---|---|
| `/scan` | Scan daily watchlist for candidates |
| `/filter` | Filter candidate scores by conditions |
| `/compare` | Compare symbols by score/setup/risk |
| `/explain` | Explain a symbol from persisted score artifacts |
| `/quality` | Show data quality status |
| `/lineage` | Show provider/ingestion/feature/scoring version |
| `/note` | Create a research note linked to a symbol |
| `/history` | Show recent research sessions |

### Multi-turn context

`ChatContext` tracks research state across turns so follow-up questions can reference prior results without repeating them. Fields:

| Field | Purpose |
|---|---|
| `chat_session_id` | Active session identifier |
| `target_date` | Research date for this session |
| `last_symbols` | Symbols seen in the most recent scan/command output |
| `selected_symbol` | Currently focused symbol |
| `selected_rank` | Rank of the selected symbol |
| `last_watchlist_date` | Date from the most recent `/scan` output |
| `last_command` | Raw text of the last slash command |
| `last_assistant_intent` | Intent string from the last assistant turn |
| `last_plan` | Serialized plan from the last assistant turn |
| `last_tool_outputs_summary` | Summary of last tool outputs |

Entity references like "the first one", "top candidate", or "that stock" are resolved to concrete symbols from `last_symbols` or `selected_symbol` before the prompt reaches the LLM.

Context is also prepended to LLM prompts as a single line, for example:

```
Context: date=2026-07-07, symbols=[VNM,VCB], selected=VNM
```

### Persistence

Phase 5.10 introduces two warehouse tables for chat persistence.

**`chat_session`** — one row per session:

```sql
CREATE TABLE IF NOT EXISTS chat_session (
    chat_session_id  VARCHAR PRIMARY KEY,
    started_at       TIMESTAMPTZ NOT NULL,
    updated_at       TIMESTAMPTZ,
    status           VARCHAR NOT NULL DEFAULT 'active',
    surface          VARCHAR NOT NULL DEFAULT 'tui-chat',
    target_date      VARCHAR,
    title            VARCHAR,
    context_json     VARCHAR
)
```

**`chat_message`** — one row per message:

```sql
CREATE TABLE IF NOT EXISTS chat_message (
    chat_message_id       VARCHAR PRIMARY KEY,
    chat_session_id       VARCHAR NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL,
    role                  VARCHAR NOT NULL,
    content               VARCHAR NOT NULL,
    message_type          VARCHAR NOT NULL DEFAULT 'plain_text',
    assistant_session_id  VARCHAR,
    research_session_id   VARCHAR,
    tool_trace_ids_json   VARCHAR,
    plan_json             VARCHAR,
    metadata_json         VARCHAR
)
```

Messages carry a `role` (`user`, `assistant`, `system`, `error`) and a `message_type`. Each message can optionally reference an `assistant_session_id` or `research_session_id` for cross-table lineage. Tool trace IDs and plan JSON are stored inline for auditability.

---

## 12.2 Keybindings

All bindings are declared in `VnAlphaApp.BINDINGS` in `src/vnalpha/tui/app.py`.

| Key | Action | Description |
|---|---|---|
| `h` | `show_home` | Push `HomeScreen` |
| `w` | `show_watchlist` | Push `WatchlistScreen` |
| `c` | `show_commands` | Push `CommandScreen` |
| `a` | `show_assistant` | Push `AssistantScreen` |
| `r` | `show_rejected` | Push `RejectedScreen` |
| `p` | `show_quality` | Push `QualityScreen` |
| `o` | `show_outcomes` | Push `OutcomeScreen` |
| `q` | `quit` | Quit the application |
| `ctrl+backslash` | `toggle_chat` | Toggle `ChatPanel` visibility |
| `ctrl+slash` | `focus_chat` | Move focus to the chat input widget |
| `Escape` | `cancel_pending_plan` | Cancel a pending plan (hidden from footer) |

The `Escape` binding posts a `PlanCancelRequested` message on the app bus. The `ChatPanel` (or any subscriber) picks this up and calls `controller.cancel_pending_plan()`.

There is also `action_approve_plan` wired on `VnAlphaApp`, which queries the chat panel's `_chat_controller` and calls `approve_pending_plan()` if a plan is pending. This action is invoked by the `a` binding when a plan is awaiting approval.

---

## 12.3 Chat-local Commands

Chat-local commands are handled directly by `ChatController.handle_chat_local_command()` without going through `CommandExecutor`. They don't touch the research slash-command registry.

### `/new`

Start a new chat session.

- Creates a `chat_session` row in the warehouse (runs migrations first).
- Resets `_chat_session_id` to the new ID.
- Clears any pending plan.
- Returns a confirmation like: `New chat session started. (id=abc12345…)`

### `/clear`

Clear the visible chat log for the current session.

```
/clear
```

Removes messages from the visible panel without deleting the persisted transcript. Returns a count: `Chat log cleared (N message(s) removed from view).`

If there's no active session, returns: `No active chat session to clear.`

### `/clear --forget`

Clear the visible log **and** permanently delete the transcript.

```
/clear --forget
```

Returns: `Chat log cleared and N message(s) deleted from transcript.`

### `/context`

Show the current session context state.

```
/context
```

Output format:

```
Current context:
  chat_session_id : <id>
  target_date     : 2026-07-07
  execution_mode  : auto
  surface         : tui-chat
  pending_plan    : none
```

All fields are conditional — fields without values are omitted. `pending_plan` shows `yes` when a plan is waiting for approval.

### `/plan`

Show or change the execution mode.

| Invocation | Effect |
|---|---|
| `/plan` | Show current mode, e.g. `Plan mode: auto` |
| `/plan on` | Set `PLAN_THEN_APPROVE` |
| `/plan off` | Set `AUTO_EXECUTE_SAFE_READ_ONLY` |
| `/plan only` | Set `PLAN_ONLY` |

### `/trace`

Show the tool trace timeline for the current session.

```
/trace
```

Output format:

```
Trace timeline (N event(s)):
  2026-07-07 10:23:01  watchlist.scan running...
  2026-07-07 10:23:02  watchlist.scan success 843ms
```

If no session is active, returns: `No active chat session — no trace available.`  
If the session has no events yet, returns: `No trace events for current session.`

### `/help`

Show all chat-local commands and research slash commands with one-line descriptions.

---

## 12.4 Plan Approval Behavior

### Execution modes

`ExecutionMode` (in `src/vnalpha/chat/modes.py`) controls what happens after the assistant produces a plan.

| Mode | String value | Behavior |
|---|---|---|
| `AUTO_EXECUTE_SAFE_READ_ONLY` | `"auto"` | Default. Executes immediately if every step in the plan is a safe read-only tool. Requires approval for anything outside the allowlist. |
| `PLAN_THEN_APPROVE` | `"plan_then_approve"` | Always shows the plan preview and waits for explicit approval before executing anything. |
| `PLAN_ONLY` | `"plan_only"` | Generates and displays the plan, but never executes it under any circumstances. |

### Plan preview format

When approval is required, the controller renders the plan as a numbered list:

```
Plan:
  1. watchlist.scan(symbols=['VNM'])
  2. fundamentals.get(symbol='VNM')

Approve? Press 'a' to approve, Esc to cancel.
```

### Approving a plan

Press `a` to invoke `action_approve_plan` on the app. This calls `controller.approve_pending_plan()`, which:

1. Clears `_pending_plan` and `_pending_plan_turn_context`.
2. Re-runs `_run_ask()` with `no_execute=False` using the original question.
3. Renders the final `AssistantAnswer.summary` in bold green, or the refusal reason in yellow.

### Canceling a plan

Press `Escape` to invoke `action_cancel_pending_plan`. This posts `PlanCancelRequested` on the app bus, which ultimately calls `controller.cancel_pending_plan()`:

- Clears `_pending_plan` and `_pending_plan_turn_context`.
- Renders `"Plan canceled."` to the chat panel.

### Safe read-only tool allowlist

The following tools are in `SAFE_READ_ONLY_TOOLS` and execute automatically in `AUTO_EXECUTE_SAFE_READ_ONLY` mode without showing a plan preview:

```python
{
    "watchlist.scan",
    "quality.get_status",
    "quality.get_many_status",
    "fundamentals.get",
    "price.get",
    "price.get_range",
    "detail.get",
    "research.explain",
    "research.compare",
}
```

Any plan that includes a tool outside this set falls back to the approval flow even in `AUTO_EXECUTE_SAFE_READ_ONLY` mode.

---

## 12.5 Research-only Safety Boundary

The chat workspace is a **research tool only**. Safety enforcement lives in `src/vnalpha/chat/safety.py`. All tool calls go through `validate_tool_call()` before execution.

### Disallowed tool name prefixes

Any tool whose name starts with one of these prefixes is blocked outright:

```python
{"broker", "order", "allocation", "account"}
```

The prefix check matches on `<prefix>_`, `<prefix>.`, or the bare prefix as an exact name. For example, `broker_connect`, `order.place`, and `account` are all blocked.

### Disallowed tool names (explicit list)

The following tool names are blocked regardless of prefix:

```
place_order        cancel_order       modify_order       submit_order
execute_order      get_holdings       rebalance          rebalance_holdings
allocate           allocate_capital   get_account        get_account_balance
transfer_funds     withdraw           deposit            connect_broker
disconnect_broker  authenticate_broker
```

### Tools requiring plan approval

The following tools are allowed in chat but **require explicit plan approval** before execution. They cannot run automatically in `AUTO_EXECUTE_SAFE_READ_ONLY` mode:

| Category | Tools |
|---|---|
| Python execution | `execute_python`, `run_python`, `eval_code`, `exec_code` |
| Web/HTTP | `web_fetch`, `http_get`, `http_post`, `fetch_url` |
| MCP calls | `mcp_call`, `mcp_invoke` |
| File writes | `write_file`, `delete_file`, `create_file`, `append_file` |

### Error messages from `validate_tool_call()`

Users see one of two error messages depending on the failure:

**Blocked tool (disallowed prefix or name):**
```
Tool '<tool_name>' is not available in research chat
```

**Tool requires approval but mode is AUTO:**
```
Tool '<tool_name>' requires plan approval. Use /plan on or switch to PLAN_THEN_APPROVE mode
```

The function returns a `(bool, str | None)` tuple. A `True` first element means the call is allowed; `False` means it's blocked with the error message in the second element.

### Design intent

This boundary enforces the core project principle: vnalpha is a research workspace, not a trading bot. The LLM can explain, summarize, scan, and compare — but it cannot place orders, touch account balances, or call broker APIs, regardless of what the user types or what the model returns. These rules are enforced at the tool-dispatch layer, not just in the prompt.
