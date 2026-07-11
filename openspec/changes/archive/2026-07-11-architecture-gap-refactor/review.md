# Review: Architecture findings and refactor rationale

## Verdict

The codebase is healthy enough for MVP operation, but it is entering a scaling-risk zone. The next features are agentic and cross-cutting, so structural cleanup is required before continuing.

Current maturity estimate:

```text
Architecture maturity:          70-75%
Directory organisation:         68-72%
TUI architecture:               75-80%
Assistant architecture:         70-75%
Command/tool architecture:      72-78%
Data pipeline architecture:     75-80%
Policy/governance structure:    45-55%
Scalability for next features:  55-65%
```

## Finding 1: `vnalpha/cli.py` is a monolithic entrypoint

The CLI currently owns too many responsibilities:

```text
Typer app creation
env loading
logging setup
sync commands
build commands
score command
watchlist command
tui launch
outcome commands
DB connection and migration setup
console rendering
```

This is acceptable for early MVP, but it will not scale when adding:

```text
/model
/context
/todo
/shortlist
/research-plan
/market-regime
```

### Required direction

Split CLI by domain while preserving `vnalpha.cli:app` as script entrypoint.

## Finding 2: Tool policy and permissions are duplicated

Permission and allowlist state exists across:

```text
vnalpha.assistant.executor ASSISTANT_TOOL_ALLOWLIST
vnalpha.assistant.planner TOOL_ALLOWLIST
vnalpha.tools.setup TOOL_PERMISSIONS
vnalpha.commands.setup permissions on CommandMeta
```

This causes policy drift.

### Required direction

Introduce a central policy module where each tool/command capability defines:

```text
name
permission
allowed_for_assistant
allowed_for_command
allowed_for_autonomous_plan
mutates_warehouse
requires_confirmation
```

Planner, executor, and registry should derive from this central policy.

## Finding 3: Assistant direct data mutation path is unsafe architecturally

`data.fetch` is currently available as a WRITE_DATA tool and appears in assistant allowlists. This creates a second data mutation path alongside deterministic data provisioning.

Current competing paths:

```text
A. deterministic ensure_symbol_analysis_ready()
B. assistant/planner directly calls data.fetch
```

### Required direction

Remove `data.fetch` from autonomous assistant allowlists. Keep it only for explicit user command/manual path if needed.

Assistant analysis should rely on deterministic pre-execution data ensure hooks.

## Finding 4: `TuiInputRouter` has too many roles

The router currently does:

```text
chat session bootstrap
ChatController setup
CommandExecutor setup
route decision
command rendering
chat rendering
status updates
busy state
approve/cancel
error capture
audit emission
```

### Required direction

Split into:

```text
routing/router.py
routing/command_path.py
routing/chat_path.py
routing/status_adapter.py
routing/lifecycle_hooks.py
```

The public behavior should remain the same.

## Finding 5: TUI layout is currently clean but lacks layout abstraction

The current layout is good:

```text
StatusBar
OutputStream
ComposerInput
FooterHint
```

But TODO panel and responsive layout will require explicit layout policy. If added directly into `app.py`, `app.py` will become a god component.

### Required direction

Introduce layout/responsive boundary before adding more UI regions.

## Finding 6: `data_availability.ensure` is a procedural workflow

The function `ensure_symbol_analysis_ready()` mixes:

```text
input normalization
checks
decision logic
actions
observability
result mutation
lazy imports
```

### Required direction

Refactor into:

```text
checks
planner
actions
service
ensure wrapper
```

Backward-compatible import path should remain.

## Finding 7: `EnsureDataResult` is too thin for downstream architecture

The result currently exposes only basic status and flags. Future analysis/TUI/assistant flows need richer freshness and lineage metadata.

### Required direction

Extend the result model with:

```text
benchmark bars
as_of_bar_date
benchmark_as_of_bar_date
provider
ingestion_run_id
feature_generated_at
score_generated_at
freshness
lineage
action durations
```

## Finding 8: Command result semantics are too coarse

Some commands return `SUCCESS` even when no data was found. This makes status/TUI/assistant handling ambiguous.

### Required direction

Add or standardise result categories:

```text
SUCCESS
EMPTY_RESULT
PARTIAL
FAILED
VALIDATION_ERROR
```

If string values must remain backward-compatible, add helper predicates and renderer mapping.

## Finding 9: Phase labels leak into architecture

Assistant and tool modules still mention Phase 5.8/5.9 in comments/docstrings. This creates stale architecture vocabulary.

### Required direction

Use capability-based naming:

```text
local tool registry
assistant tool policy
research assistant execution policy
```

## Finding 10: LLM Gateway is single-model static

Gateway currently resolves one model from env and sends that on every call.

### Required direction

Introduce model routing package and update gateway API to accept:

```text
stage
task_type
profile override
route metadata
```

Full dynamic routing can be implemented in a later dedicated PR, but the boundary must be established.

## Finding 11: Tests are skewed toward source inspection

Some TUI layout tests inspect source text rather than mounting the app and asserting DOM structure.

### Required direction

Keep source-inspection tests as guardrails, but add headless DOM tests for actual mounted widget structure.

## Finding 12: Future package boundaries must be created before features are added

Upcoming features require clear boundaries:

```text
workspace_context
model_routing
responsive_layout
todo panel
research intelligence engines
```

### Required direction

Add package skeletons and integration contracts where needed, but avoid implementing full feature behavior inside this architecture cleanup.

## Recommended priority order

```text
P0 centralise policy and remove duplicated allowlists
P0 split CLI
P0 remove assistant autonomous data.fetch
P1 refactor TUI router
P1 add model_routing boundary and gateway metadata
P1 add workspace_context boundary
P2 refactor data_availability workflow
P2 improve command result semantics
P2 add architecture tests and docs
```

## Risk if not fixed

If these gaps remain, the next capabilities will cause:

```text
policy drift
unsafe mutation paths
TUI router bloat
hard-to-debug model usage
ambiguous command results
large merge conflicts
feature-specific hacks
weak test coverage for architecture regressions
```
