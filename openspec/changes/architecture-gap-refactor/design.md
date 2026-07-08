# Design: Architecture gap refactor

## Design objective

Close the architecture gaps that block safe expansion of OpenStock into a larger terminal research workspace.

The design is intentionally incremental:

```text
move code without changing behavior
centralise policies
create package boundaries
add compatibility shims
add regression tests
```

## Refactor principles

### 1. Backward-compatible first

Existing user commands must remain valid:

```text
vnalpha init
vnalpha sync symbols
vnalpha sync ohlcv
vnalpha sync index
vnalpha build canonical
vnalpha build features
vnalpha score
vnalpha watchlist
vnalpha tui
vnalpha outcome evaluate
vnalpha outcome candidates
```

### 2. One source of truth for policy

Planner, executor, registry, and command metadata must not each define separate permissions/allowlists.

### 3. Deterministic mutation boundary

Assistant should not autonomously mutate data warehouse through `data.fetch`. Data readiness should be deterministic and explicit.

### 4. UI routing should be composable

TUI command/chat/status/context/todo/model hooks should be separate components.

### 5. No feature creep

This refactor creates architecture readiness. It should not implement full deep research, full workspace lifecycle, or full TODO side panel behavior.

## Target module changes

## 1. CLI split

### Current

```text
vnalpha/cli.py
```

### Target

```text
vnalpha/cli.py                    # compatibility shim
vnalpha/cli/
├── __init__.py
├── app.py
├── common.py
├── sync.py
├── build.py
├── score.py
├── watchlist.py
├── tui.py
└── outcome.py
```

Optional placeholders:

```text
context.py
model.py
research.py
```

### Contract

`pyproject.toml` can continue using:

```text
vnalpha = "vnalpha.cli:app"
```

`vnalpha/cli.py` should expose `app` by importing it from `vnalpha.cli.app`, or keep a thin compatibility layer if Python package/module conflict requires a different migration strategy.

If Python cannot support both `vnalpha/cli.py` and `vnalpha/cli/` simultaneously, use:

```text
vnalpha/cli_app/
```

and keep:

```python
# vnalpha/cli.py
from vnalpha.cli_app.app import app
```

Prefer `cli_app` if avoiding module/package collision.

## 2. Central policy

Add:

```text
vnalpha/policy/
├── __init__.py
├── permissions.py
├── tool_policy.py
├── command_policy.py
├── assistant_policy.py
└── safety_policy.py
```

### ToolCapability

```python
@dataclass(frozen=True)
class ToolCapability:
    name: str
    permission: ToolPermission
    allowed_for_assistant: bool
    allowed_for_command: bool
    allowed_for_autonomous_plan: bool
    mutates_warehouse: bool = False
    requires_confirmation: bool = False
```

### Required policy rule

```text
data.fetch:
  mutates_warehouse = true
  allowed_for_command = true if explicit command exists
  allowed_for_assistant = false
  allowed_for_autonomous_plan = false
```

### Consumers

Refactor these to derive policy from central definitions:

```text
assistant.executor ASSISTANT_TOOL_ALLOWLIST
assistant.planner TOOL_ALLOWLIST
tools.setup TOOL_PERMISSIONS
commands.setup command permissions
```

## 3. TUI router split

Current:

```text
vnalpha/tui/input_router.py
```

Target:

```text
vnalpha/tui/input_router.py              # compatibility import/wrapper
vnalpha/tui/routing/
├── __init__.py
├── router.py
├── command_path.py
├── chat_path.py
├── status_adapter.py
├── lifecycle_hooks.py
└── events.py
```

### Responsibilities

```text
router.py          route decision and high-level orchestration
command_path.py    CommandExecutor execution and result rendering
chat_path.py       ChatController execution and message/trace rendering
status_adapter.py  map route/tool/data events to RuntimeStatus
lifecycle_hooks.py extension point for workspace/todo/model hooks
events.py          TUI audit event helpers
```

`vnalpha.tui.input_router.TuiInputRouter` must remain importable.

## 4. Assistant data mutation boundary

Remove direct autonomous use of `data.fetch`:

```text
assistant.executor allowlist: remove data.fetch
assistant.planner TOOL_ALLOWLIST: remove data.fetch
planner fetch_data intent: refuse or direct user to explicit command
```

Acceptable behavior:

```text
User: fetch/sync data for FPT
Assistant: suggest explicit command or, if slash command path exists, instruct user to run it.
```

Analysis flows still call:

```text
ensure_symbol_analysis_ready()
```

as deterministic pre-execution hook.

## 5. Model routing boundary

Add package skeleton:

```text
vnalpha/model_routing/
├── __init__.py
├── models.py
├── config.py
├── policy.py
├── resolver.py
├── overrides.py
├── observability.py
└── integration.py
```

Minimum contract:

```python
class ModelProfile(str, Enum):
    SMALL = "small"
    DEFAULT = "default"
    REASONING = "reasoning"
    LONG_CONTEXT = "long_context"

@dataclass
class ModelRouteDecision:
    profile: ModelProfile
    model_id: str
    stage: str
    task_type: str | None
    route_reason: str
```

Update gateway signature to allow metadata:

```python
chat(messages, response_schema=None, *, stage="unknown", task_type=None, model_profile=None, route_metadata=None)
```

For this refactor, it may still resolve to the current configured model, but the API boundary must exist.

## 6. Workspace context boundary

Add package skeleton:

```text
vnalpha/workspace_context/
├── __init__.py
├── models.py
├── storage.py
├── lifecycle.py
├── compaction.py
├── cleaning.py
├── export.py
├── integration.py
└── observability.py
```

Minimum contract:

```python
@dataclass
class WorkspaceState:
    workspace_id: str
    title: str
    status: str
    updated_at: str
```

Do not implement full lifecycle unless separately scoped. Provide importable placeholders and docs for boundaries.

## 7. Data availability service split

Current public API must remain:

```python
from vnalpha.data_availability import ensure_symbol_analysis_ready
```

Target internal split:

```text
checks.py       pure DB/data status checks
planner.py      creates EnsureDataPlan/actions
actions.py      wraps sync/build/score actions
service.py      orchestrates plan execution
ensure.py       backward-compatible function wrapper
```

### Target flow

```text
check current state
build EnsureDataPlan
execute actions
check final state
return EnsureDataResult
```

This allows tests to assert planning separately from execution.

## 8. Command result semantics

Extend or standardise statuses:

```text
SUCCESS
EMPTY_RESULT
PARTIAL
FAILED
VALIDATION_ERROR
```

If the existing `CommandResult.status: str` cannot be safely changed, add constants/helpers:

```python
class CommandStatus(str, Enum): ...

def is_success(result): ...
def is_empty(result): ...
def is_partial(result): ...
```

Update `/explain` and `/compare` behavior:

```text
no candidate score/data -> EMPTY_RESULT or PARTIAL, not SUCCESS
ensure failed with no score -> FAILED or PARTIAL
warnings with usable output -> PARTIAL or SUCCESS with warnings depending policy
```

Renderers must handle new statuses.

## 9. Architecture docs

Add:

```text
vnalpha/docs/architecture.md
vnalpha/docs/package-boundaries.md
```

Update:

```text
vnalpha/docs/tui-workspace.md
```

Remove stale phase-language in core assistant/tool docs and comments.

## 10. Tests

### CLI compatibility tests

```text
vnalpha.cli exposes app
CLI app contains existing commands
sync/build/score/watchlist/tui/outcome command groups still registered
```

### Policy tests

```text
one source of truth for tool policy
data.fetch not allowed for assistant autonomous plan
assistant planner/executor allowlists derive from policy
all registered tools have policy entries
```

### TUI tests

```text
TuiInputRouter import path still works
router delegates command path
router delegates chat path
status adapter maps states
no ContentSwitcher/no secondary ChatPanel/no extra Input regression
```

### Data availability tests

```text
plan-only tests
service execution tests
ensure wrapper backward compatibility
result model includes freshness fields
```

### Command status tests

```text
/explain no score -> EMPTY_RESULT/PARTIAL
/compare no records -> EMPTY_RESULT/PARTIAL
validation errors unchanged
renderers handle all statuses
```

### Gateway/model routing boundary tests

```text
gateway accepts task_type/model_profile/route_metadata
route decision is logged or exposed in test stub
existing env model still works
```

## Validation

Implementation PR must run:

```text
make test-vnalpha
make lint-vnalpha
make verify-r4
openstock-verify --ci
```

Validation evidence should include before/after architecture notes and command compatibility confirmation.
