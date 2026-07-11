# Design: Close closed-loop logging and AI repair gaps to 100%

## Design objective

The system should support this operational loop:

```text
User/system interaction
  -> structured correlated file logs
  -> AI-readable repair bundle
  -> AI coding fix branch/PR
  -> validation gate
  -> deploy promote/reject
  -> rollback when needed
  -> deploy/rollback result logged
```

The design should remain local-first and offline-capable. External CI/CD or observability platforms may integrate later, but the base loop must work with local files and CLI commands.

## Capability groups

### 1. Unified correlation context

Use one shared correlation source for:

```text
structlog events
file-based observability events
CLI command lifecycle events
ChatController turns
tool traces
pipeline steps
repair attempts
deploy attempts
```

Implementation options:

```text
Option A: make vnalpha.core.logging delegate set/get to vnalpha.observability.context
Option B: make observability.context delegate set/get to vnalpha.core.logging
Option C: create one shared correlation module imported by both
```

Acceptance preference: one public correlation API used by both structlog and file observability.

### 2. Audit writer hardening

`log_audit()` should accept standard optional fields:

```text
module
function
session_id
object_type
object_id
extra
```

This prevents silent event loss when call sites include module/function metadata.

All event writers should use the same stable base fields:

```text
event_id
run_id
created_at
level
event_type
surface
actor
correlation_id
session_id
status
summary
module
function
redaction_status
metadata
```

### 3. CLI command lifecycle wrapper

Add a wrapper/decorator/helper around Typer commands.

Expected behavior:

```text
before command body:
  ensure run context
  create correlation_id
  log COMMAND_STARTED

after success:
  log COMMAND_SUCCEEDED
  duration_ms
  exit_code=0

after handled failure:
  log COMMAND_FAILED
  capture_exception when exception exists
  exit_code

after unhandled exception:
  capture_exception
  log COMMAND_FAILED
  re-raise or Typer exit as appropriate
```

Initial coverage:

```text
init
sync symbols
sync ohlcv
sync index
build canonical
build features
score
watchlist
cmd
ask
outcome evaluate
logs bundle/summarize/doctor
```

### 4. Script JSONL helper

Shell scripts should not hand-roll fragile JSON by echoing unescaped values.

Preferred options:

```text
Option A: packaging/scripts/openstock-log-jsonl helper using Python json.dumps
Option B: python -m vnalpha.observability.script_event ...
Option C: a shell function that safely escapes via Python
```

Required script events:

```text
PIPELINE_STARTED
PIPELINE_STEP_STARTED
PIPELINE_STEP_SUCCEEDED
PIPELINE_STEP_FAILED
PIPELINE_COMPLETED
PIPELINE_FAILED
VERIFY_STARTED
VERIFY_CHECK_PASSED
VERIFY_CHECK_WARNED
VERIFY_CHECK_SKIPPED
VERIFY_CHECK_FAILED
VERIFY_RUN_COMPLETED
BACKUP_STARTED
BACKUP_CREATED
BACKUP_FAILED
```

### 5. Repair bundle generator

Add a repair bundle generator separate from the generic log bundle.

Directory layout:

```text
logs/bundles/<bundle-id>/
├── ai-agent-summary.md
├── ai-coding-prompt.md
├── reproduction.md
├── manifest.json
├── environment.json
└── raw-logs/
    ├── audit.jsonl
    ├── app.jsonl
    ├── errors.jsonl
    ├── trace.jsonl
    └── commands.jsonl
```

`manifest.json` should include:

```text
bundle_id
created_at
source_run_ids
source_log_root
source_commit_sha
source_branch
redaction_mode
included_files
validation_commands
guardrails
checksums_or_sizes
```

`reproduction.md` should include:

```text
observed failing command(s)
expected behavior
actual behavior
exit code
stderr/stdout tail
related correlation_id(s)
```

`ai-coding-prompt.md` should include:

```text
objective
source commit/branch
observed failures
reproduction steps
relevant log excerpts
likely modules/files
constraints/guardrails
required validation commands
expected output format
```

### 6. Repair command group

Add:

```text
vnalpha repair prepare --latest
vnalpha repair status <repair-id>
vnalpha repair validate <repair-id>
```

The repair status can initially be file-backed:

```text
logs/repairs/<repair-id>/repair-status.json
```

or stored inside the bundle manifest. File-backed is preferred for local-first operation.

Repair events:

```text
REPAIR_PREPARED
REPAIR_STARTED
REPAIR_BRANCH_RECORDED
REPAIR_PR_RECORDED
REPAIR_VALIDATION_STARTED
REPAIR_VALIDATION_PASSED
REPAIR_VALIDATION_FAILED
REPAIR_ACCEPTED
REPAIR_REJECTED
REPAIR_DEFERRED
```

### 7. Repair validation

`repair validate` should run a safe, configurable validation command list.

Default command list:

```text
make test-vnalpha
make lint-vnalpha
make verify-r0
make verify-r2-ci
make verify-r4
openstock-verify --ci
```

The command may support dry-run mode for environments where full execution is unavailable.

Validation result should include:

```text
command
status
exit_code
duration_ms
stdout_tail
stderr_tail
started_at
ended_at
```

### 8. Deploy command group

Add:

```text
vnalpha deploy verify
vnalpha deploy promote <candidate>
vnalpha deploy rollback <deployment-id>
```

Initial implementation may be dry-run or local package-aware. It must still log events and enforce gates.

Promotion rules:

```text
if no repair validation exists: block
if validation failed: block
if candidate commit/version missing: block
if deploy verify failed: block
if explicit override is used: log override reason and actor
```

Deploy events:

```text
DEPLOY_VERIFY_STARTED
DEPLOY_VERIFY_PASSED
DEPLOY_VERIFY_FAILED
DEPLOY_BLOCKED
DEPLOY_PROMOTED
POST_DEPLOY_SMOKE_PASSED
POST_DEPLOY_SMOKE_FAILED
ROLLBACK_STARTED
ROLLBACK_SUCCEEDED
ROLLBACK_FAILED
```

### 9. End-to-end fixture

Add a fixture test that simulates:

```text
1. Failed command writes commands/errors/audit logs.
2. Summary is generated.
3. repair prepare creates bundle.
4. repair validate records failed validation.
5. deploy promote is blocked.
6. Event trail is present and parseable.
```

A second dry-run scenario may simulate successful validation and deploy event logging without real production deployment.

## Safety guardrails

All repair/deploy prompts and manifests must include:

```text
No broker/order/account/portfolio/margin/trading execution.
Do not bypass tests/review/deploy verification.
Do not modify safety boundaries to pass tests.
Default redaction must remain enabled.
Do not include .env, keys, tokens, cookies, or private credentials in bundles.
```

## Testing strategy

Add or extend tests for:

```text
correlation unification
log_audit module/function compatibility
CLI lifecycle wrapper success/failure
script JSONL escaping/parseability
pipeline step event emission
verify check event emission
backup failure event emission
repair bundle generation
repair prompt generation
repair manifest contents
repair status and validation result logging
deploy gate blocks missing/failed validation
deploy dry-run success event logging
rollback event logging
closed-loop fixture
```

## Validation report

Add a validation document after implementation:

```text
openspec/changes/close-closed-loop-logging-gaps-100/validation.md
```

It should include command outputs or summarized evidence for:

```text
make test-vnalpha
make lint-vnalpha
make verify-r0
make verify-r2-ci
make verify-r4
openstock-verify --ci
repair prepare fixture
repair validate fixture
deploy promote blocked fixture
deploy/rollback dry-run fixture
```
