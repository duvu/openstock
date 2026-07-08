# Design: File-based observability for AI-agent-readable logs

## Design principles

1. **File-first**: logs must be useful without any external service.
2. **Structured by default**: JSONL is the raw event format.
3. **AI-readable entrypoint**: each run has a markdown summary.
4. **Correlation everywhere**: related events share a `correlation_id`.
5. **Audit is not debug**: activity/audit events are separate from app noise.
6. **Redacted by default**: sensitive runtime values are not written unless explicitly enabled.
7. **Best effort, never crash**: logging failures must not crash core workflows.
8. **Stable contract**: schemas define required fields and allowed event families.

## Proposed package layout

```text
vnalpha/src/vnalpha/observability/
├── __init__.py
├── context.py
├── jsonl.py
├── logger.py
├── audit.py
├── errors.py
├── commands.py
├── trace.py
├── summary.py
├── bundle.py
├── redaction.py
└── schemas.py
```

## Runtime log layout

Default package/deploy path:

```text
/var/log/openstock/
```

Default local-dev fallback:

```text
~/.local/state/openstock/logs/
```

A config value or environment variable may override this root.

Each run creates:

```text
runs/<run-id>/
├── audit.jsonl
├── app.jsonl
├── errors.jsonl
├── trace.jsonl
├── commands.jsonl
├── ai-agent-summary.md
├── environment.json
└── README.md
```

`latest` points to the newest run directory when symlinks are available. If symlinks are not available, write a `latest.txt` pointer file.

## Run ID model

A `run_id` identifies a top-level process or user-facing session.

Examples:

```text
cli_<timestamp>_<shortid>
tui_<timestamp>_<shortid>
pipeline_<timestamp>_<shortid>
verify_<timestamp>_<shortid>
backup_<timestamp>_<shortid>
```

## Correlation ID model

A `correlation_id` identifies a workflow inside a run.

Examples:

```text
corr_cmd_<shortid>
corr_chat_<shortid>
corr_tool_<shortid>
corr_pipeline_step_<shortid>
```

A single run may contain many correlation IDs.

## Event files

### `audit.jsonl`

Purpose: meaningful activity trail.

Examples:

```text
COMMAND_EXECUTED
COMMAND_FAILED
CHAT_TURN_CREATED
PLAN_PREVIEWED
PLAN_APPROVED
PLAN_CANCELLED
TOOL_REFUSED
PIPELINE_STARTED
PIPELINE_COMPLETED
VERIFY_RUN_COMPLETED
BACKUP_CREATED
WAREHOUSE_MIGRATION_RUN
```

### `commands.jsonl`

Purpose: CLI/TUI/chat command execution details.

Required details:

```text
command
args
surface
status
exit_code
duration_ms
stdout_tail
stderr_tail
correlation_id
```

### `trace.jsonl`

Purpose: reconstruct a workflow timeline.

Required details:

```text
span_id
parent_span_id
correlation_id
event_type
status
started_at
ended_at
duration_ms
module
operation
```

### `errors.jsonl`

Purpose: focused error and warning review.

Required details:

```text
error_id
level
error_type
error_message
stacktrace
stacktrace_hash
module
function
correlation_id
likely_cause
suggested_next_step
```

Warnings should be written when they indicate degraded behavior, data quality problems, skipped validation, or recoverable failures.

### `app.jsonl`

Purpose: lower-level development logs.

This file may include debug/info lifecycle events. It should not be the primary audit source.

## AI summary format

`ai-agent-summary.md` SHALL include:

```text
# AI Agent Run Summary

## Run
- run_id
- started_at
- ended_at
- branch
- commit
- command or surface
- result

## What happened

## Errors

## Warnings

## Failed commands

## Suspicious patterns

## Files or modules likely involved

## Suggested investigation

## Raw logs
```

The summary generator SHALL mark likely causes and suggestions as non-authoritative.

## Redaction

Add a redaction module that scans keys and values before writing logs. It SHALL redact common secret-like fields and configurable custom patterns.

Content logging mode:

```text
OPENSTOCK_LOG_CONTENT=metadata | redacted | full
```

Default SHALL be `redacted` or safer.

`metadata` mode records only shape, type, IDs, counts, and hashes.

`redacted` mode records content after redaction.

`full` mode records full content and must be explicit opt-in.

## Shell script logging

Shell scripts may log JSONL directly or invoke a small helper command. Required scripts:

```text
packaging/scripts/openstock-run-pipeline
packaging/scripts/openstock-verify
packaging/scripts/openstock-backup-warehouse
```

If direct JSONL is used, scripts must avoid invalid JSON and must include run/correlation IDs.

## CLI commands

Add a `logs` command group or equivalent:

```text
vnalpha logs latest
vnalpha logs show --latest
vnalpha logs errors --latest
vnalpha logs bundle --latest
vnalpha logs summarize --latest
vnalpha logs doctor --latest
```

Expected behavior:

- `latest`: print latest run path.
- `show`: print summary and recent events.
- `errors`: print recent errors/warnings.
- `bundle`: create a portable archive or bundle directory.
- `summarize`: regenerate `ai-agent-summary.md` from JSONL.
- `doctor`: inspect logs for common failure patterns.

## Testing strategy

Add tests for:

```text
JSONL append writes valid JSON lines
run directory creation
latest pointer behavior
schema-required fields
redaction behavior
correlation ID propagation
error capture with stack trace
command event status and output tails
summary generation
bundle generation
best-effort failure behavior
```

## Rollout plan

### Step 1: Core file sink

Implement run directory creation, JSONL writer, redaction, and schema helpers.

### Step 2: Command and error logging

Instrument CLI command path and central exception capture.

### Step 3: Chat and tool flow logging

Instrument ChatController, AssistantApp, CommandExecutor, and tool execution.

### Step 4: Pipeline and deploy script logging

Instrument pipeline, verify, backup, and restore scripts.

### Step 5: AI summary and bundle commands

Add summary and bundle commands for agent handoff.

## Compatibility

This change does not replace existing DuckDB persistence. Chat transcripts, tool traces, and domain results remain in DuckDB. File logs provide an operational narrative and support artifact.
