# Design: Architecture gap remediation

## Design objective

Close structural architecture gaps without changing the product boundary.

The design must preserve:

```text
read-only research boundary
existing CLI command compatibility
existing TUI single-composer workflow
existing assistant plan/execute/synthesize flow
existing data pipeline behavior
```

while improving package boundaries and eliminating duplicated policy logic.

## Target dependency direction

Recommended high-level dependency direction:

```text
cli/tui/chat/assistant/commands
        ↓
policy / model_routing / workspace_context adapters
        ↓
tools / data_availability / scoring / features / ingestion
        ↓
warehouse / clients / core / observability
```

Rules:

```text
- core must not import application layers
- warehouse must not import TUI/assistant/commands
- scoring/features/ingestion must not import TUI/assistant
- tools may call domain modules but must not own business policy
- assistant must consume policy; it must not define independent tool policy
- TUI must call router/path adapters; it must not own domain logic
```

## CLI refactor design

Current console script should remain:

```text
vnalpha = "vnalpha.cli:app"
```

To preserve that, convert `vnalpha/cli.py` into a compatibility module:

```python
from vnalpha.cli.app import app
```

Target tree:

```text
vnalpha/src/vnalpha/cli.py
vnalpha/src/vnalpha/cli/
├── __init__.py
├── app.py
├── common.py
├── sync.py
├── build.py
├── score.py
├── watchlist.py
├── tui.py
├── outcome.py
├── context.py
├── model.py
└── research.py
```

`common.py` owns:

```text
_load_dotenv
configure_app_logging
get_conn_with_migrations
common Typer options if useful
```

`app.py` owns:

```text
root Typer app
sub-app registration
callback registration
```

Each command module owns only its command group and minimal rendering.

## Central policy design

Add:

```text
vnalpha/src/vnalpha/policy/
├── __init__.py
├── permissions.py
├── tool_policy.py
├── assistant_policy.py
├── command_policy.py
└── safety_policy.py
```

### `permissions.py`

Defines canonical permissions:

```text
READ_WATCHLIST
READ_SCORE
READ_QUALITY
READ_LINEAGE
READ_HISTORY
WRITE_NOTE
WRITE_DATA
ADMIN_CONTEXT
ADMIN_MODEL
```

Can reuse or re-export existing `ToolPermission` initially to avoid large migration.

### `tool_policy.py`

Single source of truth:

```python
@dataclass(frozen=True)
class ToolPolicyEntry:
    name: str
    permission: ToolPermission
    allowed_for_command: bool
    allowed_for_assistant: bool
    mutates_warehouse: bool
    requires_confirmation: bool = False
```

Expected policy:

```text
watchlist.scan              assistant yes, command yes
watchlist.filter            assistant yes, command yes
candidate.explain           assistant yes, command yes
candidate.compare           assistant yes, command yes
quality.get_status          assistant yes, command yes
quality.get_many_status     assistant yes, command yes
lineage.get_symbol_lineage  assistant yes, command yes
note.create                 assistant yes or confirm depending policy
history.list_sessions       assistant yes, command yes
data.fetch                  assistant no, command/manual yes, mutates warehouse yes
```

### `assistant_policy.py`

Provides:

```python
get_assistant_tool_allowlist() -> frozenset[str]
assert_assistant_tool_allowed(tool_name: str) -> None
```

Planner and executor must consume this.

### `command_policy.py`

Provides command permission metadata helpers, reused by `commands.setup`.

## Tool registry migration

`tools.setup` should no longer define independent policy. It should consume policy:

```text
TOOL_PERMISSIONS = tool_policy.permission_map()
```

`build_local_tool_registry()` may remain in `tools.setup`, but tool metadata should come from central policy.

## Assistant allowlist migration

Remove hardcoded allowlists from:

```text
assistant.executor
assistant.planner
```

Replace with:

```text
from vnalpha.policy.assistant_policy import get_assistant_tool_allowlist
```

Planner validation and executor checks must use the same source.

Remove assistant support for autonomous `fetch_data` intent or convert it into a refusal/manual-command suggestion.

## TUI router refactor design

Target tree:

```text
vnalpha/src/vnalpha/tui/routing/
├── __init__.py
├── router.py
├── command_path.py
├── chat_path.py
├── status_adapter.py
├── lifecycle_hooks.py
└── events.py
```

### `router.py`

Owns only:

```text
input normalization
route decision
busy guard
shortcut routing for /clear /approve /cancel
calls command/chat path
```

### `command_path.py`

Owns:

```text
CommandExecutor setup
command execution in worker thread
command result rendering
command warnings/status mapping
```

### `chat_path.py`

Owns:

```text
ChatController setup
chat session bootstrap
chat execution in worker thread
trace callback wiring
approve/cancel wrappers
```

### `status_adapter.py`

Owns:

```text
RuntimeStatus mapping
command result status -> TUI status
trace event -> TUI status
```

### `lifecycle_hooks.py`

Future integration point for:

```text
workspace context input record
todo panel refresh
model status display
```

MVP can include no-op hooks.

### Compatibility

`vnalpha.tui.input_router.TuiInputRouter` may remain as a shim importing/aliasing the new router class, or it can delegate to the new router to avoid breaking imports.

## Command result status semantics

Extend or standardize status values:

```text
SUCCESS
PARTIAL
EMPTY
FAILED
VALIDATION_ERROR
```

Rules:

```text
SUCCESS: expected data/output produced
PARTIAL: useful output produced with incomplete data or warnings
EMPTY: valid command but no matching data/result
FAILED: runtime failure
VALIDATION_ERROR: invalid input
```

Update renderers and TUI status adapter accordingly.

Update handlers:

```text
/explain no candidate score -> EMPTY or PARTIAL depending ensure state
/compare no scores -> EMPTY
/scan no candidates -> EMPTY
/filter no rows -> EMPTY
```

## data_availability refactor design

Keep public API backward compatible:

```python
ensure_symbol_analysis_ready(conn, symbol, target_date, *, policy=DEFAULT_POLICY) -> EnsureDataResult
```

Internally refactor to:

```text
DataAvailabilityService.ensure_symbol_analysis_ready
  -> DataAvailabilityChecker.collect_state
  -> DataAvailabilityPlanner.plan_actions
  -> DataAvailabilityExecutor.execute_actions
  -> DataAvailabilityChecker.collect_state
  -> EnsureDataResult.from_state_and_actions
```

New files:

```text
planner.py
actions.py
executor.py
service.py
```

### Enriched result

Add optional fields without breaking existing panels:

```text
benchmark_bars
as_of_bar_date
benchmark_as_of_bar_date
freshness
lineage
action_durations
provider
```

Existing `to_panel_dict()` should remain.

## model_routing boundary

If full runtime routing is implemented elsewhere, this remediation should create package skeleton and docs only:

```text
vnalpha/src/vnalpha/model_routing/__init__.py
vnalpha/src/vnalpha/model_routing/README.md or docs reference
```

If implemented here, keep it minimal and do not hardwire providers.

## workspace_context boundary

If full runtime workspace context is implemented elsewhere, this remediation should create package skeleton and docs only:

```text
vnalpha/src/vnalpha/workspace_context/__init__.py
vnalpha/src/vnalpha/workspace_context/README.md or docs reference
```

TUI should integrate through future `lifecycle_hooks.py`, not direct imports scattered in app/router.

## Tests

### Architecture tests

Add:

```text
tests/test_architecture_boundaries.py
```

Checks:

```text
assistant planner/executor consume central assistant policy
no hardcoded ASSISTANT_TOOL_ALLOWLIST outside policy module
no data.fetch in assistant allowlist
commands import policy metadata
cli compatibility import works
```

### CLI tests

```text
vnalpha.cli:app imports
root app contains existing command groups
legacy command names still registered
```

### TUI routing tests

```text
TuiInputRouter import compatibility remains
new router has command/chat/status path components
clear/approve/cancel behavior preserved
one OutputStream / one ComposerInput / one Input layout constraints remain
```

### Command status tests

```text
/explain missing score returns EMPTY/PARTIAL, not SUCCESS
/compare no scores returns EMPTY
renderer handles EMPTY/PARTIAL
TUI status maps EMPTY/PARTIAL to warning/ready as defined
```

### data availability tests

```text
public ensure API still works
planned actions match missing data state
executor runs dependency-injected actions
result includes enriched fields when available
cache hit still works
```

## Docs

Add:

```text
vnalpha/docs/architecture.md
vnalpha/docs/package-boundaries.md
```

Update:

```text
vnalpha/docs/tui-workspace.md
```

Docs must include:

```text
current package tree
allowed dependency direction
policy source of truth
CLI module organization
TUI routing organization
data availability flow
future package boundaries
```

## Validation

Implementation PR should run:

```text
make test-vnalpha
make lint-vnalpha
make verify-r4
openstock-verify --ci
```

Validation evidence should include:

```text
CLI compatibility
assistant no data.fetch allowlist
architecture boundary tests
TUI layout tests
command status tests
data availability API compatibility
```
