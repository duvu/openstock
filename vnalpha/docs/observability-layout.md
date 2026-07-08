# Observability Log Layout

## Overview

vnalpha writes structured file-based logs for every CLI command, TUI session, chat turn, tool execution, pipeline step, and domain operation.

## Log root

| Priority | Path | Condition |
|----------|------|-----------|
| 1st | `$VNALPHA_LOG_ROOT` | When env var is set |
| 2nd | `/var/log/openstock` | When writable (deployed) |
| 3rd | `~/.local/state/openstock/logs` | Local dev fallback |

## Directory structure

```
$LOG_ROOT/
├── runs/
│   ├── latest -> runs/<run-id>/        (symlink, or latest.txt fallback)
│   ├── latest.txt                      (text fallback if symlinks unavailable)
│   └── <run-id>/
│       ├── audit.jsonl         Meaningful activity trail
│       ├── app.jsonl           Low-level lifecycle logs
│       ├── errors.jsonl        Exceptions, warnings, degraded behavior
│       ├── trace.jsonl         Workflow/tool/pipeline timeline spans
│       ├── commands.jsonl      CLI/TUI/chat command details
│       ├── ai-agent-summary.md Human/AI-readable narrative
│       ├── environment.json    Git, Python, platform metadata
│       └── README.md           File meanings
└── schemas/
    ├── audit-event.schema.json
    ├── app-log.schema.json
    ├── error-event.schema.json
    ├── trace-event.schema.json
    └── command-event.schema.json
```

## Run ID format

```
<surface>_<timestamp>_<shortid>
cli_20260708T123456_abc12345
tui_20260708T130000_def67890
pipeline_20260708T200000_ghi11111
```

## File meanings

### `audit.jsonl`
Meaningful user/system activity events. Key event types:
- `COMMAND_EXECUTED`, `COMMAND_FAILED`
- `CHAT_TURN_STARTED`
- `PLAN_PREVIEWED`, `PLAN_APPROVED`, `PLAN_CANCELLED`
- `TOOL_REFUSED`
- `PIPELINE_STARTED`, `PIPELINE_COMPLETED`
- `VERIFY_RUN_COMPLETED`
- `BACKUP_CREATED`
- `WAREHOUSE_MIGRATION_RUN`
- `SYNC_COMPLETED`, `FEATURE_BUILD_COMPLETE`, `SCORING_COMPLETE`
- `OUTCOME_EVALUATION_COMPLETE`

### `app.jsonl`
Lower-level development/lifecycle log entries. Not the primary audit source.

### `errors.jsonl`
Exceptions, warnings, and degraded-behavior events. Includes:
- `error_type`, `error_message`
- `stacktrace`, `stacktrace_hash` (md5)
- `likely_cause` (when inferrable)
- `suggested_next_step` (when useful)

### `trace.jsonl`
Workflow/tool/pipeline timeline spans. Includes:
- `span_id`, `parent_span_id`
- `started_at`, `ended_at`, `duration_ms`
- `operation`, `module`

### `commands.jsonl`
CLI/TUI/chat command execution details. Includes:
- `command`, `args`
- `status`, `exit_code`, `duration_ms`
- `stdout_tail`, `stderr_tail` (bounded to 2 KB)

### `ai-agent-summary.md`
Human and AI-readable run narrative. Auto-generated from JSONL files.

### `environment.json`
Git branch/commit, Python version, platform, log_root, started_at.

## Content modes

| Mode | Description | Env var |
|------|-------------|---------|
| `redacted` | Sensitive keys replaced with `[REDACTED]` (default) | `VNALPHA_LOG_CONTENT_MODE=redacted` |
| `metadata` | Only safe metadata fields logged (IDs, counts, hashes) | `VNALPHA_LOG_CONTENT_MODE=metadata` |
| `full` | Raw content including prompts/answers — explicit opt-in | `VNALPHA_LOG_CONTENT_MODE=full` |

## Correlation IDs

Every event has a `correlation_id` linking related audit, trace, command, app, and error events for a single workflow.

## Retention

Runs are never automatically deleted. Clean up old runs manually:
```bash
find ~/.local/state/openstock/logs/runs -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
```
