# Review: Architecture gaps and remediation rationale

## Verdict

OpenStock / vnalpha is in a workable MVP state, but the architecture is approaching a complexity boundary.

Current maturity:

```text
Data pipeline:              good MVP structure
Command path:               good base, needs policy consolidation
Assistant path:             good base, duplicated allowlists
TUI path:                   good UX direction, router too stateful
Policy/governance:          weak and scattered
Future extensibility:       at risk without remediation
```

The next features — workspace context, TODO side rail, model routing, deep research intelligence — should not be added directly into existing large files.

## Finding 1: CLI entrypoint is too large

`vnalpha/cli.py` owns too many responsibilities:

```text
Typer root app
sub-app registration
env loading
logging setup
warehouse connections
sync commands
build commands
score commands
watchlist rendering
tui launch
outcome commands
```

This makes future command growth risky.

### Recommendation

Split into `vnalpha/cli/` modules and keep `vnalpha/cli.py` as a compatibility shim.

## Finding 2: Policy and permissions are duplicated

Currently, tool and assistant allowlists exist in multiple places:

```text
assistant.executor.ASSISTANT_TOOL_ALLOWLIST
assistant.planner.TOOL_ALLOWLIST
tools.setup.TOOL_PERMISSIONS
tools.setup.build_local_tool_registry
commands.setup command permissions
```

This creates drift and safety risk.

### Recommendation

Create central policy modules:

```text
vnalpha/policy/permissions.py
vnalpha/policy/tool_policy.py
vnalpha/policy/assistant_policy.py
vnalpha/policy/command_policy.py
```

All registries should consume these definitions.

## Finding 3: Assistant should not autonomously mutate warehouse data

The assistant currently has `data.fetch` in tool allowlists. That is a `WRITE_DATA` tool.

But data readiness is already handled by deterministic `data_availability.ensure`.

### Recommendation

Remove `data.fetch` from assistant autonomous plan/execution allowlists.

Allowed pattern:

```text
assistant candidate.explain/candidate.compare
  -> deterministic pre-execution ensure data
  -> analysis tool reads resulting artifacts
```

Disallowed pattern:

```text
assistant decides to call data.fetch as a tool step
```

Manual or command-driven data sync can remain, but it should be explicit.

## Finding 4: TUI router is doing too much

`TuiInputRouter` currently coordinates:

```text
chat session bootstrap
ChatController setup
CommandExecutor setup
route decision
command execution
chat execution
approve/cancel
status bar updates
rendering callbacks
busy state
observability
error capture
```

This will not scale with workspace context hooks, TODO panel refresh, and model status display.

### Recommendation

Split into route/path/status components:

```text
vnalpha/tui/routing/router.py
vnalpha/tui/routing/command_path.py
vnalpha/tui/routing/chat_path.py
vnalpha/tui/routing/status_adapter.py
vnalpha/tui/routing/lifecycle_hooks.py
vnalpha/tui/routing/events.py
```

Keep current public behavior stable.

## Finding 5: Command result status semantics are too coarse

Some handlers return success for no-data outcomes. That creates poor downstream behavior for TUI status, assistant synthesis, and automation.

### Recommendation

Extend `CommandResult.status` to distinguish:

```text
SUCCESS
PARTIAL
EMPTY
FAILED
VALIDATION_ERROR
```

If a command finds no score/watchlist/record, it should return `EMPTY`, not `SUCCESS`.

If a command produces output but has warnings or incomplete data, it should return `PARTIAL`.

## Finding 6: data_availability is useful but procedural

The current ensure function mixes:

```text
input normalization
checks
planning
actions
logging
result assembly
```

### Recommendation

Split into:

```text
checks.py
planner.py
actions.py
executor.py
service.py
models.py
policy.py
observability.py
```

Desired flow:

```text
DataAvailabilityService.ensure_symbol_analysis_ready
  -> check current state
  -> build action plan
  -> execute action plan
  -> final check
  -> return rich result
```

## Finding 7: EnsureDataResult should be richer

The current result is too sparse for TUI, assistant context, and future deep analysis.

### Recommendation

Add fields such as:

```text
benchmark_bars
as_of_bar_date
benchmark_as_of_bar_date
provider
ingestion_run_id
feature_generated_at
score_generated_at
freshness
lineage
action_durations
```

## Finding 8: LLM model selection is static

The gateway currently uses one configured model. Future work needs model profile routing.

### Recommendation

Introduce `vnalpha/model_routing/` package boundary and route model selection by stage/task profile.

If runtime implementation is handled in a separate OpenSpec, this remediation should at least reserve and document the boundary.

## Finding 9: Workspace context needs a package boundary

Workspace context should not be embedded in TUI router or command handlers.

### Recommendation

Introduce `vnalpha/workspace_context/` package boundary and keep TUI/assistant integrations as adapters.

## Finding 10: TUI layout tests should move from source inspection toward DOM behavior

Source inspection can catch obvious regressions, but mounted TUI behavior matters more.

### Recommendation

Add tests for:

```text
one OutputStream
one ComposerInput
one Textual Input
StatusBar visible
Composer focus
no ContentSwitcher mounted
no secondary ChatPanel mounted
future TodoPanel responsive visibility
```

## Risk of doing nothing

If architecture remediation is deferred, future changes will likely produce:

```text
large `cli.py`
large `TuiInputRouter`
duplicated allowlists
ambiguous permissions
assistant warehouse mutation risk
inconsistent command statuses
hard-to-test UI behavior
```

## MVP remediation boundary

Do now:

```text
split CLI
centralize policy
remove assistant data.fetch
split TUI router responsibility
normalize command result statuses
create/stub model_routing and workspace_context boundaries
add architecture tests/docs
```

Defer to separate OpenSpecs:

```text
full model routing runtime
full workspace context runtime
responsive TODO panel runtime
deep research intelligence runtime
```
