# Proposal: Workspace context lifecycle

## Summary

Add a file-backed workspace context system so users can resume work across TUI sessions and manage the lifecycle of accumulated research context.

The system should support:

```text
workspace state persistence
resume previous workspace
compact context into summary artifacts
clean noisy or stale context
start a new workspace
inspect context status
export context bundle
```

Primary user-facing commands:

```text
/context status
/context compact
/context clean
/context new
/context resume
/context export
```

Convenience aliases may be added:

```text
/compact
/clean
/new
/resume
/status
```

This OpenSpec defines runtime implementation requirements.

## Why

The TUI is evolving into an opencode-like research workspace. A single session may include:

```text
user questions
slash commands
assistant answers
tool traces
data provisioning actions
watchlist results
shortlist experiments
symbol analysis
warnings/errors
research notes
```

Without lifecycle management, the workspace becomes noisy. The next session cannot reliably continue from where the user stopped, and the assistant cannot know which symbols, dates, watchlists, assumptions, and pending tasks are currently active.

## Problem statement

OpenStock needs a durable workspace context layer separate from raw audit logs.

Raw logs are for observability. Workspace context is for continuity.

The system should distinguish:

```text
audit logs      -> immutable evidence of what happened
chat history    -> conversation transcript
workspace state -> current working memory and resumable context
compact summary -> condensed context for future continuation
```

The user needs explicit lifecycle commands:

```text
compact -> summarize and reduce context size
clean   -> remove or archive noisy/stale context
new     -> start a fresh workspace
resume  -> load existing workspace
status  -> inspect context health
export  -> save/share context bundle
```

## Goals

- Add a workspace context domain model.
- Persist active workspace data to files.
- Load the latest or selected workspace on startup.
- Track active symbols, target date, watchlist state, shortlist state, analysis outputs, scenario outputs, notes, pending tasks, and data freshness.
- Keep raw event logs separate from curated workspace state.
- Add compacting logic that turns verbose history into a concise summary while preserving key decisions and open tasks.
- Add cleaning logic that archives or removes stale/noisy context according to policy.
- Add new-workspace logic that safely starts a clean workspace without deleting audit logs.
- Add status reporting for context size, age, active artifacts, stale data, and compaction need.
- Add export bundle for handoff/debugging.
- Integrate commands with CLI, TUI composer, assistant, and observability.
- Preserve privacy and redaction boundaries.

## Non-goals

- Do not use workspace context as a substitute for audit logs.
- Do not delete audit logs when cleaning context.
- Do not silently discard user notes.
- Do not store secrets, tokens, credentials, or raw sensitive values.
- Do not allow context summaries to invent facts not present in source artifacts.
- Do not require a remote service to resume context.
- Do not add account/allocation/execution functionality.

## Proposed workspace storage

Default file layout:

```text
.vnalpha/workspaces/
├── latest -> <workspace-id>/
├── <workspace-id>/
│   ├── workspace.json
│   ├── context.md
│   ├── compact.md
│   ├── events.jsonl
│   ├── artifacts/
│   │   ├── watchlist.json
│   │   ├── shortlist.json
│   │   ├── analysis/<symbol>.json
│   │   └── scenario/<symbol>.json
│   └── exports/
└── archive/
```

Alternative config may place this under the configured vnalpha data/log root.

## Workspace model

Minimum fields:

```text
workspace_id
created_at
updated_at
title
status
active_date
active_symbols
active_watchlist_id
active_shortlist_id
recent_commands
recent_questions
active_artifacts
open_tasks
assumptions
warnings
errors
data_freshness
last_compacted_at
context_size
```

## Lifecycle commands

### `/context status`

Show:

```text
workspace id/title
age and last updated time
active symbols/date
context size
last compaction time
open tasks
warning/error count
stale artifacts
suggested action
```

### `/context compact`

Create or update `compact.md` from current workspace data.

Compaction should keep:

```text
current goal
active symbols
active date
important findings
decisions and assumptions
latest watchlist/shortlist state
open tasks
warnings/errors
links to source artifacts
```

Compaction should remove or de-emphasize:

```text
duplicate command outputs
repeated tool traces
transient errors already resolved
verbose tables that exist as artifacts
old drafts not referenced by current work
```

### `/context clean`

Clean current workspace according to policy.

Modes:

```text
/context clean --dry-run
/context clean --resolved-errors
/context clean --old-events
/context clean --artifacts
/context clean --all-noisy
```

Clean should archive before deleting when feasible.

### `/context new`

Start a new workspace.

Behavior:

```text
- compact current workspace first unless --no-compact
- mark previous workspace archived or inactive
- create new workspace id
- update latest symlink/pointer
- reset active symbols/tasks/transient state
- keep audit logs untouched
```

### `/context resume`

Resume latest or named workspace.

Behavior:

```text
/context resume
/context resume <workspace-id>
/context list
```

### `/context export`

Create a portable context bundle:

```text
workspace.json
compact.md
context.md
selected artifacts
manifest.json
```

## Critique and design constraints

### Context is not memory dump

The system should not simply append everything forever. That creates stale, misleading state.

### Compact must be evidence-linked

A compact summary should link back to source files/artifacts and include timestamps.

### Clean must be safe

Clean should never erase audit logs or user-authored notes without explicit confirmation or archival.

### New must not lose work

Starting a new workspace should compact/archive the old workspace by default.

### Resume must make state explicit

On resume, TUI should show what was loaded:

```text
Resumed workspace <id>: active date, active symbols, open tasks, last compacted time.
```

### Assistant must know workspace context source

Assistant should consume `compact.md` and current workspace metadata as context, not raw unbounded transcripts.

## Success criteria

This change is complete when:

```text
- workspace files are created on first TUI/CLI workspace use
- user inputs and important outputs update workspace state
- /context status reports current workspace health
- /context compact writes compact.md
- /context clean supports dry-run and safe archival
- /context new creates a new workspace and archives previous state safely
- /context resume loads latest or selected workspace
- /context export creates a portable bundle
- TUI shows workspace id/status
- assistant can use compact workspace context when answering follow-up questions
- audit logs remain separate and untouched
- tests cover lifecycle operations and safety boundaries
```

## Completion principle

Do not mark this complete by only saving chat transcripts. The feature must manage workspace lifecycle: persist, resume, compact, clean, new, status, and export.
