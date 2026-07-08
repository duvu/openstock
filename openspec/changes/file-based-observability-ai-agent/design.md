# Design: File-based observability and closed-loop AI repair

## Design principles

1. **File-first**: logs must be useful without any external service.
2. **Structured by default**: JSONL is the raw event format.
3. **AI-readable entrypoint**: each run has a markdown summary.
4. **Repair-ready evidence**: logs can be bundled into a coding-agent prompt.
5. **Correlation everywhere**: related events share a `correlation_id`.
6. **Audit is not debug**: activity/audit events are separate from app noise.
7. **Redacted by default**: sensitive runtime values are not written unless explicitly enabled.
8. **Evidence-gated repair**: fixes must pass tests and deploy verification before promotion.
9. **Best effort, never crash**: logging failures must not crash core workflows.
10. **Stable contract**: schemas define required fields and allowed event families.

## Closed-loop target flow

```text
1. Runtime interaction
   User runs CLI/TUI/chat/pipeline.

2. Observe
   System writes activity, command, trace, warning, and error events to files.

3. Summarize
   System generates ai-agent-summary.md.

4. Package evidence
   User or automation runs repair prepare to create an AI coding bundle.

5. AI coding
   Agent reads ai-coding-prompt.md + selected logs and proposes/implements a fix.

6. Validate
   Required tests, lint, verify, and smoke commands run and are logged.

7. Promote or reject
   Candidate is promoted only when gates pass, or rejected/deferred with reason.

8. Deploy/rollback
   Deploy result and rollback path are logged.

9. Repeat
   The improved system continues to generate better logs.
```

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
├── repair.py
├── deploy.py
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

Repair bundles create:

```text
bundles/<bundle-id>/
├── ai-agent-summary.md
├── ai-coding-prompt.md
├── reproduction.md
├── manifest.json
├── environment.json
└── raw-logs/
    ├── audit.jsonl
    ├── errors.jsonl
    ├── trace.jsonl
    └── commands.jsonl
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
repair_<timestamp>_<shortid>
deploy_<timestamp>_<shortid>
```

## Correlation ID model

A `correlation_id` identifies a workflow inside a run.

Examples:

```text
corr_cmd_<shortid>
corr_chat_<shortid>
corr_tool_<shortid>
corr_pipeline_step_<shortid>
corr_repair_<shortid>
corr_deploy_<shortid>
```

A single run may contain many correlation IDs. A repair bundle may reference multiple source run IDs.

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
REPAIR_PREPARED
REPAIR_VALIDATED
REPAIR_ACCEPTED
REPAIR_REJECTED
DEPLOY_VERIFY_STARTED
DEPLOY_PROMOTED
DEPLOY_ROLLED_BACK
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

### repair/deploy events

Repair and deploy events may live in `audit.jsonl` with distinct `event_type`, or in dedicated files later. They must include:

```text
repair_id
deployment_id
source_run_ids
source_commit_sha
fix_branch
pr_number
candidate_commit_sha
previous_version
candidate_version
validation_status
deploy_status
rollback_status
```

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

## AI coding prompt format

`ai-coding-prompt.md` SHALL include:

```text
# AI Coding Repair Prompt

## Objective

## Source runs and commit

## Observed failure

## Reproduction steps

## Relevant log excerpts

## Likely files/modules to inspect

## Required constraints

## Required validation commands

## Expected output
- proposed fix summary
- changed files
- commands run
- validation result
- risks/deferred items
```

The prompt must tell the coding agent not to add broker/order/account/portfolio/trading execution features.

## Redaction

Add a redaction module that scans keys and values before writing logs, summaries, and bundles. It SHALL redact common secret-like fields and configurable custom patterns.

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

Add a `repair` command group or equivalent:

```text
vnalpha repair prepare --latest
vnalpha repair status <repair-id>
vnalpha repair validate <repair-id>
```

Add a deploy command group or integrate equivalent scripts:

```text
vnalpha deploy verify
vnalpha deploy promote <candidate>
vnalpha deploy rollback <deployment-id>
```

Expected behavior:

- `logs latest`: print latest run path.
- `logs show`: print summary and recent events.
- `logs errors`: print recent errors/warnings.
- `logs bundle`: create a portable archive or bundle directory.
- `logs summarize`: regenerate `ai-agent-summary.md` from JSONL.
- `logs doctor`: inspect logs for common failure patterns.
- `repair prepare`: create AI coding bundle from logs.
- `repair status`: show repair state, branch, PR, commit, and validation.
- `repair validate`: run required validation commands and record results.
- `deploy verify`: verify candidate can be deployed.
- `deploy promote`: promote candidate only after gates pass or explicit override.
- `deploy rollback`: restore prior version and log verification result.

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
repair bundle generation
AI coding prompt generation
repair status and validation logging
deploy gate blocking when validation fails
deploy dry-run/promotion event logging
rollback event logging
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

Instrument pipeline, verify, backup, restore, deploy verify, promote, and rollback scripts.

### Step 5: AI summary and log bundle commands

Add summary and bundle commands for agent handoff.

### Step 6: AI repair bundle commands

Add repair preparation, repair status, and repair validation commands.

### Step 7: Closed-loop deployment gates

Add deploy verification, promotion gate, rollback logging, and post-deploy smoke logging.

## Compatibility

This change does not replace existing DuckDB persistence. Chat transcripts, tool traces, and domain results remain in DuckDB. File logs provide an operational narrative and support artifact.

The repair loop is AI-assisted, not uncontrolled self-modification. Promotion remains evidence-gated and must record validation/deploy results.
