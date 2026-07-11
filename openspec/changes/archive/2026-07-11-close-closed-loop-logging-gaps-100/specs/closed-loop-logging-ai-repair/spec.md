# Specification: Closed-loop logging and AI repair gap closure

## ADDED Requirements

### Requirement: Correlation IDs shall be unified across logging systems

OpenStock SHALL use one shared correlation source for structured logging and file-based observability.

#### Scenario: CLI command produces one correlation ID

- **GIVEN** a CLI command starts
- **WHEN** it writes command, audit, trace, or error events
- **THEN** all related events SHALL share the same non-empty correlation ID
- **AND** the correlation ID SHALL NOT be `unset`.

#### Scenario: Chat turn produces one correlation ID

- **GIVEN** a ChatController natural-language turn starts
- **WHEN** it writes prompt, plan, tool, answer, refusal, trace, or error events
- **THEN** all related events SHALL share the same correlation ID.

#### Scenario: Tool call inherits parent correlation

- **GIVEN** a command or chat flow calls a tool
- **WHEN** the tool writes trace and audit events
- **THEN** those events SHALL use the parent flow correlation ID unless a child span ID is used for step detail.

---

### Requirement: Audit writer shall accept standard metadata fields

The audit writer SHALL accept optional metadata without losing events.

#### Scenario: Module metadata is accepted

- **GIVEN** a call site emits `log_audit(..., module="vnalpha.tools")`
- **WHEN** the event is written
- **THEN** the event SHALL be written to `audit.jsonl`
- **AND** the module value SHALL be recorded.

#### Scenario: Unsupported optional metadata does not drop event

- **GIVEN** a call site includes optional metadata fields
- **WHEN** the writer receives them
- **THEN** the event SHALL still be persisted
- **AND** unknown metadata SHALL be placed under `metadata` or ignored explicitly without raising.

#### Scenario: Tool refusal is auditable

- **GIVEN** a tool call is refused by permission policy
- **WHEN** the refusal occurs
- **THEN** `TOOL_REFUSED` SHALL be written to `audit.jsonl`.

---

### Requirement: CLI commands shall emit lifecycle file events

Major Typer commands SHALL emit command lifecycle events.

#### Scenario: Command succeeds

- **GIVEN** an instrumented CLI command runs successfully
- **WHEN** the command completes
- **THEN** `commands.jsonl` SHALL contain `COMMAND_STARTED` and `COMMAND_SUCCEEDED`
- **AND** the success event SHALL include duration and exit code.

#### Scenario: Command fails

- **GIVEN** an instrumented CLI command fails
- **WHEN** the command exits
- **THEN** `commands.jsonl` SHALL contain `COMMAND_STARTED` and `COMMAND_FAILED`
- **AND** `errors.jsonl` SHALL contain an exception or failure event when an exception exists.

#### Scenario: Commands are covered consistently

- **GIVEN** users run core CLI commands
- **WHEN** they run init, sync, build, score, watchlist, cmd, ask, outcome evaluate, or logs commands
- **THEN** each command SHALL emit lifecycle events.

---

### Requirement: Runtime warnings and swallowed exceptions shall be captured

Recoverable and swallowed errors SHALL still be visible to AI agents.

#### Scenario: Swallowed exception is logged

- **GIVEN** a best-effort path catches an exception to preserve UX
- **WHEN** the exception is swallowed
- **THEN** `errors.jsonl` SHALL contain a structured error event.

#### Scenario: Data quality warning is logged

- **GIVEN** a workflow continues with stale data, missing data, missing benchmark, skipped validation, or degraded behavior
- **WHEN** the warning is known
- **THEN** a warning event SHALL be written to `errors.jsonl`.

---

### Requirement: Tool lifecycle shall be observable

Tool execution SHALL be reconstructable from file logs.

#### Scenario: Tool succeeds

- **GIVEN** a local tool is executed successfully
- **WHEN** it completes
- **THEN** `trace.jsonl` SHALL contain started and succeeded events
- **AND** the events SHALL include tool name, duration, correlation ID, and span ID.

#### Scenario: Tool fails

- **GIVEN** a local tool raises an error
- **WHEN** the failure occurs
- **THEN** `trace.jsonl` SHALL contain a failed event
- **AND** `errors.jsonl` SHALL contain useful error details where available.

#### Scenario: Tool is refused

- **GIVEN** a local tool is blocked by permission policy
- **WHEN** the refusal occurs
- **THEN** audit/trace events SHALL record the refusal.

---

### Requirement: Pipeline script shall log step-level JSONL events

`openstock-run-pipeline` SHALL log every pipeline step, not only start/end.

#### Scenario: Pipeline step succeeds

- **GIVEN** a pipeline step runs successfully
- **WHEN** the step completes
- **THEN** `commands.jsonl` or an equivalent file SHALL contain `PIPELINE_STEP_STARTED` and `PIPELINE_STEP_SUCCEEDED`.

#### Scenario: Pipeline step fails

- **GIVEN** a pipeline step fails
- **WHEN** the script exits
- **THEN** the script SHALL write `PIPELINE_STEP_FAILED`
- **AND** SHALL write `PIPELINE_FAILED` before exit when feasible.

#### Scenario: Script output is valid JSONL

- **GIVEN** the pipeline script writes JSONL
- **WHEN** each line is parsed
- **THEN** every line SHALL be valid JSON.

---

### Requirement: Verify script shall log check-level JSONL events

`openstock-verify` SHALL write structured events for each check.

#### Scenario: Check passes

- **GIVEN** a verify check passes
- **WHEN** the check records status
- **THEN** a `VERIFY_CHECK_PASSED` event SHALL be written.

#### Scenario: Check warns or skips

- **GIVEN** a verify check warns or is skipped
- **WHEN** the check records status
- **THEN** `VERIFY_CHECK_WARNED` or `VERIFY_CHECK_SKIPPED` SHALL be written.

#### Scenario: Check fails

- **GIVEN** a verify check fails
- **WHEN** the check records status
- **THEN** a `VERIFY_CHECK_FAILED` event SHALL be written.

#### Scenario: Verify summary is written

- **GIVEN** verify completes
- **WHEN** final status is known
- **THEN** `VERIFY_RUN_COMPLETED` SHALL include pass/warn/fail counts.

---

### Requirement: Backup and restore paths shall log failures and success

Operational data protection scripts SHALL be auditable.

#### Scenario: Backup is blocked by lock

- **GIVEN** a pipeline lock exists
- **WHEN** backup exits because the lock is present
- **THEN** `BACKUP_FAILED` SHALL be written with the lock reason.

#### Scenario: Warehouse file is missing

- **GIVEN** the warehouse file does not exist
- **WHEN** backup exits
- **THEN** `BACKUP_FAILED` SHALL be written with the missing path.

#### Scenario: Backup copy fails

- **GIVEN** copy operation fails
- **WHEN** backup exits
- **THEN** `BACKUP_FAILED` SHALL be written.

#### Scenario: Backup succeeds

- **GIVEN** backup succeeds
- **WHEN** the backup file exists
- **THEN** `BACKUP_CREATED` SHALL be written with backup path metadata.

---

### Requirement: Repair preparation shall produce an AI coding bundle

The system SHALL generate a coding-agent-ready repair bundle from logs.

#### Scenario: Repair bundle is created from latest run

- **GIVEN** a latest run exists
- **WHEN** the user runs `vnalpha repair prepare --latest`
- **THEN** a bundle SHALL be created under `logs/bundles/<bundle-id>/`.

#### Scenario: Repair bundle contains required files

- **GIVEN** a repair bundle is created
- **WHEN** its contents are inspected
- **THEN** it SHALL contain `ai-agent-summary.md`, `ai-coding-prompt.md`, `reproduction.md`, `manifest.json`, `environment.json`, and selected raw logs.

#### Scenario: Repair prepared event is written

- **GIVEN** repair bundle generation succeeds
- **WHEN** the bundle is finalized
- **THEN** `REPAIR_PREPARED` SHALL be written.

---

### Requirement: AI coding prompt shall be actionable and safe

`ai-coding-prompt.md` SHALL contain enough context for a coding agent to fix the issue safely.

#### Scenario: Prompt contains repair context

- **GIVEN** repair bundle generation runs
- **WHEN** `ai-coding-prompt.md` is written
- **THEN** it SHALL include objective, source commit/branch, observed failures, reproduction steps, relevant log excerpts, likely files/modules, constraints, validation commands, and expected output format.

#### Scenario: Prompt includes guardrails

- **GIVEN** repair prompt is generated
- **WHEN** it is read
- **THEN** it SHALL explicitly prohibit broker/order/account/portfolio/margin/trading execution features
- **AND** SHALL prohibit bypassing validation/deploy gates.

#### Scenario: Prompt separates facts from inference

- **GIVEN** likely causes or suggested fixes are included
- **WHEN** the prompt is written
- **THEN** they SHALL be labeled as likely/suggested rather than confirmed fact.

---

### Requirement: Repair status and validation shall be tracked

AI-assisted repair attempts SHALL be auditable.

#### Scenario: Repair status is available

- **GIVEN** a repair ID exists
- **WHEN** the user runs `vnalpha repair status <repair-id>`
- **THEN** the command SHALL show bundle ID, source run IDs, branch/PR/commit metadata where available, and validation status.

#### Scenario: Repair validation records results

- **GIVEN** repair validation runs
- **WHEN** validation completes
- **THEN** each command result SHALL be recorded with status, exit code, duration, and output tails.

#### Scenario: Repair validation failure is recorded

- **GIVEN** one validation command fails
- **WHEN** validation completes
- **THEN** `REPAIR_VALIDATION_FAILED` SHALL be written
- **AND** the repair status SHALL be failed.

---

### Requirement: Deploy promotion shall be gated

Deployment promotion SHALL require validation evidence.

#### Scenario: Promotion is blocked without validation

- **GIVEN** a candidate has no repair validation result
- **WHEN** promotion is attempted
- **THEN** promotion SHALL be blocked
- **AND** `DEPLOY_BLOCKED` SHALL be written.

#### Scenario: Promotion is blocked after failed validation

- **GIVEN** repair validation failed
- **WHEN** promotion is attempted
- **THEN** promotion SHALL be blocked
- **AND** the block reason SHALL be logged.

#### Scenario: Promotion records success

- **GIVEN** validation and deploy verification pass
- **WHEN** the candidate is promoted
- **THEN** `DEPLOY_PROMOTED` SHALL be written with previous and candidate versions.

#### Scenario: Rollback is recorded

- **GIVEN** rollback is executed
- **WHEN** rollback completes
- **THEN** rollback result SHALL be written with source and target versions.

---

### Requirement: Closed-loop fixture shall prove the workflow

The repo SHALL include an automated or dry-run fixture proving the closed loop.

#### Scenario: Failure creates repair bundle and blocks deploy

- **GIVEN** a safe fixture command fails
- **WHEN** logs are summarized and repair prepare runs
- **THEN** the repair bundle SHALL be created
- **AND** repair validation failure SHALL be recorded
- **AND** deploy promotion SHALL be blocked with a logged reason.

#### Scenario: Dry-run success records deploy events

- **GIVEN** a dry-run candidate passes validation
- **WHEN** deploy verification and promotion run in dry-run mode
- **THEN** deploy verify and promotion events SHALL be written without performing unsafe production deployment.

---

### Requirement: Completion shall require validation evidence

The change SHALL NOT be marked complete without evidence.

#### Scenario: Validation report is committed

- **GIVEN** implementation is complete
- **WHEN** the change is marked ready
- **THEN** `validation.md` SHALL contain evidence for tests, lint, verify, repair prepare, repair validate, deploy gate, and rollback/dry-run scenarios.

#### Scenario: Tasks remain unchecked until evidenced

- **GIVEN** a task lacks runtime evidence
- **WHEN** tasks are reviewed
- **THEN** the task SHALL remain unchecked.
