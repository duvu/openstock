# Design: Workspace context lifecycle

## Design objective

Add a durable workspace context layer for the terminal research workspace.

The design must support:

```text
persist current work
resume later
compact noisy history into useful summary
clean stale/noisy context safely
start a new workspace
export a handoff bundle
inject bounded context into assistant workflows
```

## Architecture overview

Add package:

```text
vnalpha/src/vnalpha/workspace_context/
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

Add command handlers:

```text
vnalpha/src/vnalpha/commands/handlers/context.py
```

Optional CLI app group:

```text
vnalpha context status
vnalpha context compact
vnalpha context clean
vnalpha context new
vnalpha context resume
vnalpha context list
vnalpha context export
```

TUI composer commands:

```text
/context status
/context compact
/context clean
/context new
/context resume
/context list
/context export
```

Convenience aliases:

```text
/compact
/clean
/new
/resume
/status
```

## Storage design

Default path:

```text
.vnalpha/workspaces/
```

Configurable by environment/config:

```text
VNALPHA_WORKSPACE_ROOT
```

Workspace layout:

```text
.vnalpha/workspaces/
├── latest.json
├── index.json
├── <workspace-id>/
│   ├── workspace.json
│   ├── context.md
│   ├── compact.md
│   ├── events.jsonl
│   ├── artifacts/
│   │   ├── watchlist.json
│   │   ├── shortlist.json
│   │   ├── analysis/
│   │   └── scenario/
│   ├── archive/
│   └── exports/
└── archive/
```

Use `latest.json` instead of symlink for portability.

All writes should be atomic:

```text
write temp file
fsync when feasible
rename into place
```

Use file locks or lock files for write operations:

```text
<workspace-id>/.lock
```

## Workspace model

`models.py` should include:

```python
@dataclass
class WorkspaceState:
    workspace_id: str
    title: str
    status: str
    mode: str | None
    created_at: str
    updated_at: str
    active_date: str | None
    active_symbols: list[str]
    active_artifacts: list[WorkspaceArtifactRef]
    recent_inputs: list[WorkspaceInputRef]
    open_tasks: list[WorkspaceTask]
    assumptions: list[str]
    warnings: list[str]
    errors: list[str]
    data_freshness: dict[str, Any]
    last_compacted_at: str | None
    context_size: dict[str, Any]
```

Supporting models:

```python
WorkspaceArtifactRef
WorkspaceInputRef
WorkspaceTask
WorkspaceStatusReport
CompactionResult
CleanPlan
CleanResult
ExportResult
```

## Events

`events.jsonl` is curated workspace event stream, not raw audit log.

Event types:

```text
WORKSPACE_CREATED
WORKSPACE_RESUMED
WORKSPACE_INPUT_ADDED
WORKSPACE_ARTIFACT_ADDED
WORKSPACE_CONTEXT_UPDATED
WORKSPACE_COMPACT_STARTED
WORKSPACE_COMPACTED
WORKSPACE_CLEAN_DRY_RUN
WORKSPACE_CLEANED
WORKSPACE_ARCHIVED
WORKSPACE_NEW_STARTED
WORKSPACE_EXPORTED
WORKSPACE_ERROR
```

Each event should include:

```text
event_id
created_at
workspace_id
event_type
summary
metadata
source_ref
redaction_status
```

## Lifecycle service

`lifecycle.py` should provide:

```python
get_or_create_latest_workspace(root=None) -> WorkspaceState
create_workspace(title=None, mode=None, root=None) -> WorkspaceState
resume_workspace(workspace_id=None, root=None) -> WorkspaceState
list_workspaces(root=None) -> list[WorkspaceState]
archive_workspace(workspace_id, root=None) -> WorkspaceState
get_status(workspace_id=None, root=None) -> WorkspaceStatusReport
record_input(workspace, text, input_kind, source="tui") -> None
record_artifact(workspace, artifact_ref) -> None
record_warning(workspace, warning) -> None
record_error(workspace, error) -> None
```

## Context files

### `workspace.json`

Machine-readable current state.

### `context.md`

Human-readable live workspace context.

Should include:

```text
workspace title/id
active objective
active date
active symbols
recent important inputs
active artifacts
open tasks
warnings/errors
```

### `compact.md`

Compacted summary for assistant continuation.

Should include:

```text
current goal
active symbols/date
important findings
decisions/assumptions
latest watchlist/shortlist status
open tasks
warnings/errors
source artifact references
generated_at
```

## Compaction design

`compact` should be deterministic first. It may use LLM later only behind explicit policy.

MVP deterministic compaction should summarise from:

```text
workspace.json
curated events.jsonl
artifact summaries
warnings/errors
open tasks
```

Compaction should not consume raw audit logs by default.

`compact.md` must include source references:

```text
source: events.jsonl#event_id
source: artifacts/watchlist.json
source: artifacts/analysis/FPT.json
```

Compaction result:

```text
CompactionResult
- workspace_id
- compact_path
- before_size
- after_size
- preserved_items
- archived_items
- warnings
```

## Cleaning design

`clean` should support:

```text
--dry-run
--resolved-errors
--old-events
--artifacts
--all-noisy
--older-than DAYS
--archive-first true|false
```

Default:

```text
/context clean
```

should behave as dry-run unless explicit destructive flag is provided.

Clean plan should classify items:

```text
keep
archive
remove
needs_confirmation
```

Never clean:

```text
audit logs
compact.md
workspace.json
user-pinned items
user-authored notes
```

## New workspace design

`/context new` should:

```text
1. load current workspace
2. compact current workspace unless --no-compact
3. archive current workspace or mark inactive
4. create new workspace
5. update latest.json
6. render summary of switch
```

Options:

```text
/context new --title "FPT deep analysis"
/context new --mode symbol-analysis
/context new --no-compact
```

## Resume design

`/context resume` should resume latest workspace.

```text
/context resume <workspace-id>
/context list
```

On resume, output should show:

```text
workspace id/title
mode
active date
active symbols
open tasks
warnings/errors
last compacted time
```

## Export design

`export` should create a bundle under:

```text
<workspace>/exports/<timestamp>-context-bundle/
```

Bundle files:

```text
manifest.json
workspace.json
compact.md
context.md
artifacts selected by policy
checksums.txt
```

Optional archive:

```text
context-bundle.zip
```

## Assistant integration

Assistant should load bounded context:

```text
compact.md
workspace.json summary
selected active artifact summaries
```

Do not inject raw events by default.

Suggested integration point:

```text
ChatController -> AssistantApp -> context provider -> planner/synthesizer messages
```

The assistant must treat workspace context as stale unless freshness metadata says otherwise. Fresh warehouse data remains authoritative.

## TUI integration

TUI should show workspace identity in status bar or header:

```text
workspace=<title-or-id> mode=<mode> compact=<age> dirty=<yes/no>
```

On startup:

```text
resume latest workspace by default
or create first workspace if none exists
```

On every submitted input:

```text
record sanitized input metadata and text when safe
update recent_inputs
write workspace event
```

Important outputs should be recorded as artifact refs, not pasted wholesale.

## Command result rendering

Each `/context` command should return structured panels:

```text
Workspace Status
Compaction Summary
Clean Plan
New Workspace
Resume Summary
Export Bundle
```

## Observability

Workspace lifecycle should emit both workspace events and audit events.

Audit event examples:

```text
WORKSPACE_CREATED
WORKSPACE_RESUMED
WORKSPACE_COMPACTED
WORKSPACE_CLEANED
WORKSPACE_NEW_STARTED
WORKSPACE_EXPORTED
WORKSPACE_ERROR
```

Audit metadata should avoid raw sensitive text unless redacted.

## Tests

Required tests:

```text
create workspace creates files
resume latest loads workspace
record input updates workspace and events
compact writes compact.md
clean dry-run does not delete files
clean archive-first moves files to archive
new compacts old and creates fresh workspace
export creates manifest and bundle
assistant context provider loads compact only
TUI startup creates/resumes workspace
/context commands return structured CommandResult
observability events emitted
atomic write does not corrupt workspace on failure
```

## Documentation

Add:

```text
vnalpha/docs/workspace-context-lifecycle.md
```

Include:

```text
conceptual model
file layout
commands
compact/clean/new/resume behavior
safety boundaries
diagnostics
examples
```

## Validation

Implementation PR should run:

```text
make test-vnalpha
make lint-vnalpha
make verify-r4
openstock-verify --ci
```

Validation evidence should include a mocked or temp-dir lifecycle test:

```text
new -> record input -> compact -> status -> export -> new -> resume old
```
