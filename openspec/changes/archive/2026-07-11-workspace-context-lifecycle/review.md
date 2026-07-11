# Review: Workspace context lifecycle critique and ideas

## Verdict

A file-backed workspace context layer is necessary, but it must be designed carefully. If it becomes a raw transcript dump, it will make the assistant less reliable, not more reliable.

Correct target:

```text
curated, resumable, compact workspace state
```

Incorrect target:

```text
unbounded chat logs reused as memory
```

## Main critique

### 1. Raw history is not context

Every command, trace, warning, table, and assistant reply is not equally important. A workspace needs current state and durable decisions, not every byte of past output.

### 2. Context needs lifecycle, not just persistence

Saving files is insufficient. The user needs explicit lifecycle controls:

```text
status
compact
clean
new
resume
export
```

Without lifecycle commands, the workspace will become stale and ambiguous.

### 3. Audit logs and workspace state must be separate

Audit logs are immutable evidence. Workspace context is curated working memory. Cleaning workspace context must not delete audit records.

### 4. Compaction must be structured

A compact summary should not be a vague paragraph. It should preserve:

```text
current objective
active symbols/date
important findings
latest artifacts
assumptions
decisions
open tasks
warnings/errors
source links
```

### 5. Clean must be safe by default

`clean` should start with dry-run. Destructive clean should archive first or require explicit flags.

### 6. New workspace must not lose work

`new` should compact/archive the current workspace before switching unless the user explicitly disables it.

### 7. Resume should be transparent

When resuming, the TUI should show exactly what was loaded:

```text
workspace id
active date
active symbols
open tasks
last compacted time
warnings/errors
```

### 8. Assistant context injection must be bounded

The assistant should consume:

```text
compact.md
workspace.json
selected artifact summaries
```

It should not blindly consume raw `events.jsonl` or complete transcripts.

## Additional ideas

### Idea 1: Workspace modes

Add workspace modes:

```text
research
watchlist-review
symbol-analysis
shortlist-building
scenario-planning
debugging
```

Mode helps compacting and status display.

### Idea 2: Workspace title auto-generation

Generate default title from first meaningful task:

```text
2026-07-08 Watchlist review
FPT deep analysis
Banking sector shortlist
```

### Idea 3: Context health score

`/context status` should show a health score:

```text
GOOD       compacted recently, no stale data, few unresolved errors
WARN       large context or stale artifacts
DIRTY      many unresolved errors/no recent compaction
STALE      old active date or stale data
```

### Idea 4: Artifact references instead of copying huge payloads

Workspace should store references to large artifacts:

```text
artifact_id
path
summary
hash
created_at
```

Do not paste large tables repeatedly into context.md.

### Idea 5: Pins

Allow users to pin important context so clean/compact preserves it:

```text
/context pin FPT
/context pin "Watch banking sector tomorrow"
/context unpin <id>
```

Pins can be a later enhancement, but the model should allow it.

### Idea 6: Task list

Workspace should keep open tasks:

```text
- Review FPT after fresh data sync
- Compare FPT/MWG/HPG
- Build shortlist for banking sector
```

Future commands:

```text
/context task add ...
/context task done ...
```

### Idea 7: Workspace diff

Useful for review/debugging:

```text
/context diff
/context diff <workspace-id-a> <workspace-id-b>
```

Later enhancement.

### Idea 8: Context budget

Track size budgets:

```text
events_count
context_md_bytes
compact_md_bytes
artifact_count
estimated_tokens
```

If budget exceeds threshold, status should recommend compact/clean.

## Proposed MVP boundary

MVP should implement:

```text
workspace model
file storage
status
compact
clean dry-run
new
resume latest/by id
export
TUI display
assistant compact context injection
observability events
tests
```

Defer:

```text
pins
task management UI
workspace diff
persistent semantic memory
multi-user workspace sharing
```

## Risk assessment

### Risk: context summaries hallucinate

Mitigation: compacting must be deterministic or strongly grounded in source artifacts. If LLM summarization is used, it must cite local source artifact IDs and preserve missing-data caveats.

### Risk: accidental data loss

Mitigation: archive-first clean and new. Audit logs never deleted.

### Risk: sensitive values stored

Mitigation: apply redaction, skip sensitive-looking inputs, and store metadata instead of raw payload when needed.

### Risk: workspace conflicts

Mitigation: lock workspace writes and use atomic file replacement.

### Risk: assistant over-trusts stale context

Mitigation: every resumed context should include timestamps and stale warnings. Fresh data must remain authoritative.
