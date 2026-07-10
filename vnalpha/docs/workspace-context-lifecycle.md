# Workspace context lifecycle

Workspace context is vnalpha's durable, curated working memory for a research session. It preserves the state needed to continue work without treating a chat transcript or audit trail as the source of truth.

## What belongs where

| Store | Purpose |
| --- | --- |
| Workspace state | Current research context, including active symbols, open tasks, warnings, artifacts, and recent safe inputs. |
| `context.md` | A readable view of the current workspace state. |
| `compact.md` | A bounded summary for continuing work later. |
| `events.jsonl` | Curated workspace lifecycle events. |
| Audit logs | Immutable operational evidence. They are separate from workspace context. |
| Warehouse data | Current market and research data. This remains authoritative when it conflicts with an older workspace summary. |

Workspace summaries are not a data source and may be stale. Check fresh warehouse data before relying on a saved date, result, or finding.

## Storage layout

By default, workspaces are stored under `.vnalpha/workspaces`. Set `VNALPHA_WORKSPACE_ROOT` to use another root, for example:

```bash
VNALPHA_WORKSPACE_ROOT=/srv/vnalpha/workspaces vnalpha cmd "/context status"
```

The root contains a portable latest-workspace pointer and an index. Each workspace has its own files:

```text
.vnalpha/workspaces/
├── latest.json
├── index.json
├── <workspace-id>/
│   ├── workspace.json
│   ├── context.md
│   ├── compact.md
│   ├── events.jsonl
│   ├── .lock
│   ├── artifacts/
│   └── exports/
└── archive/
```

`workspace.json` is the machine readable state. `context.md` is regenerated from that state. `compact.md` is written when the workspace is compacted. `latest.json` identifies the active workspace, and `index.json` lists known workspace ids. Files written by the workspace store use atomic replacement to avoid partial JSON files.

## Commands

Run these commands in the vnalpha command surface, such as `vnalpha cmd "..."` or the TUI composer.

| Command | Alias | Result |
| --- | --- | --- |
| `/context status` | `/status` | Shows workspace identity, mode, active date and symbols, open task count, warnings, errors, update and compaction times, context size, and a suggested action when applicable. |
| `/context compact` | `/compact` | Writes or refreshes `compact.md` from curated workspace state. |
| `/context clean` | `/clean` | Shows a cleanup plan by default. Use `--execute` to apply it. |
| `/context new` | `/new` | Archives the current workspace and starts a new one. It compacts first unless `--no-compact` is supplied. |
| `/context resume [workspace-id]` | `/resume` | Resumes the latest workspace, or the named workspace id. |
| `/context list` | None | Lists available workspace ids, titles, modes, statuses, and update times. |
| `/context export [workspace-id]` | None | Creates a portable bundle for the selected workspace or the active workspace. |

`/context` with no subcommand behaves as `/context status`.

## Lifecycle behavior

### Compact

`/context compact` creates or updates `compact.md`, records when compaction ran, and preserves the active workspace state needed for continuation. The summary is derived from curated workspace data, not raw audit logs. It is intended to keep important state visible while avoiding an unbounded history.

### Clean

`/context clean` is a dry run by default. It reports a plan that classifies entries as keep, archive, remove, or needing confirmation. It does not archive or delete files until you use `--execute`.

```text
/context clean
/context clean --execute
/context clean --resolved-errors
/context clean --resolved-errors --execute
```

Destructive cleanup uses `--execute`. Before removing an eligible workspace item, the cleanup process copies it to `<workspace-root>/archive/<workspace-id>/`. The clean plan protects `workspace.json`, `compact.md`, active artifacts, pinned items, and user-authored notes. Audit logs are outside this cleanup boundary and must remain untouched.

### New

`/context new` safely changes the active workspace:

1. It compacts the current workspace by default.
2. It marks that workspace as archived.
3. It creates a new active workspace and updates `latest.json`.

Use `--no-compact` only when you intentionally want to skip the summary step:

```text
/context new
/context new --no-compact
```

Starting a new workspace does not remove audit logs.

### Resume and list

`/context resume` loads the workspace named by `latest.json`. Passing an id resumes that workspace and makes it the latest one. The resume result includes its title, status, mode, active date and symbols, open task count, and last compaction time.

Use `/context list` before resuming an older workspace when you need its id.

### Export

`/context export` creates a timestamped bundle in the workspace `exports/` directory. The bundle contains `manifest.json`, `workspace.json`, `context.md`, `compact.md` when available, and approved active artifacts. The manifest records the exported file list and checksums.

## Safety boundaries

* Workspace context is curated working memory, not a raw transcript dump.
* Workspace events are separate from immutable audit evidence. Lifecycle actions must not delete audit logs.
* Sensitive-looking inputs are redacted or skipped before they are stored. Audit metadata should prefer safe metadata such as input kind and length over raw text.
* Compaction does not ingest raw audit logs by default.
* Clean is dry-run first. Review the plan, then add `--execute` only when the proposed changes are acceptable.
* Cleanup is archive-first. Protected workspace files and user-authored material stay out of the cleanup set.
* Treat saved context as potentially stale. Query current warehouse data for authoritative market or research values.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| No workspace exists yet | Run `/context status` or `/context resume`. A workspace is created when there is no latest workspace. |
| You need to inspect cleanup without changing files | Run `/context clean` without `--execute`. |
| You need to skip the automatic summary before starting over | Run `/context new --no-compact`. |
| You need an earlier session | Run `/context list`, then `/context resume <workspace-id>`. |
| A summary disagrees with current data | Treat the summary as stale context and refresh the relevant warehouse data. |
| Workspace files are in an unexpected location | Check `VNALPHA_WORKSPACE_ROOT`; otherwise use the default `.vnalpha/workspaces` path. |
| An artifact listed in status is missing | Run `/context status` and then compact after resolving or replacing the missing artifact. |

## Practical examples

Check the active workspace before continuing research:

```bash
vnalpha cmd "/context status"
```

Save a compact handoff point, then inspect it in the workspace directory:

```bash
vnalpha cmd "/context compact"
```

Preview cleanup, apply it only after reviewing the plan, then export a handoff bundle:

```bash
vnalpha cmd "/context clean"
vnalpha cmd "/context clean --execute"
vnalpha cmd "/context export"
```

Start a fresh line of research while retaining the previous workspace as an archived, compacted record:

```bash
vnalpha cmd "/context new"
vnalpha cmd "/context list"
vnalpha cmd "/context resume ws-20260710T120000-abcdef"
```
