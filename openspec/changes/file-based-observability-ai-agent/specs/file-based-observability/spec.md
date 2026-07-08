# Specification: File-based observability for AI-agent-readable logs

## ADDED Requirements

### Requirement: System shall write AI-readable logs to files

OpenStock SHALL write structured operational logs to disk so a human or AI agent can inspect runtime behavior after execution.

#### Scenario: CLI run creates a log run directory

- **GIVEN** a user runs a `vnalpha` CLI command
- **WHEN** the command starts
- **THEN** OpenStock SHALL create or reuse a run directory for that command
- **AND** the run directory SHALL contain JSONL log files or create them on first write.

#### Scenario: TUI launch creates a log run directory

- **GIVEN** a user launches `vnalpha tui`
- **WHEN** the TUI starts
- **THEN** OpenStock SHALL create a TUI run directory
- **AND** all TUI lifecycle, chat, command, and error events SHALL be associated with that run.

#### Scenario: Pipeline wrapper creates a log run directory

- **GIVEN** `openstock-run-pipeline` is executed
- **WHEN** the pipeline starts
- **THEN** OpenStock SHALL create a pipeline run directory
- **AND** pipeline step events SHALL be written under that run.

---

### Requirement: Log directory layout shall be stable

OpenStock SHALL use a stable file layout for AI-agent handoff.

#### Scenario: Run directory contains standard files

- **GIVEN** a run directory is created
- **WHEN** the run records events
- **THEN** the directory SHALL contain or be able to contain `audit.jsonl`, `app.jsonl`, `errors.jsonl`, `trace.jsonl`, `commands.jsonl`, `ai-agent-summary.md`, `environment.json`, and `README.md`.

#### Scenario: Latest run is discoverable

- **GIVEN** at least one run exists
- **WHEN** a user or AI agent requests the latest run
- **THEN** OpenStock SHALL expose the latest run through a `latest` symlink or equivalent pointer file.

#### Scenario: Log root is configurable

- **GIVEN** the default log root is not writable
- **WHEN** OpenStock initializes logging
- **THEN** it SHALL fall back to a local user-writable path
- **AND** SHALL record the selected path in environment metadata where possible.

---

### Requirement: JSONL events shall be structured and parseable

Every JSONL line SHALL be a complete JSON object that can be parsed independently.

#### Scenario: Event line is valid JSON

- **GIVEN** an event is written
- **WHEN** the line is read independently
- **THEN** it SHALL parse as valid JSON.

#### Scenario: Event includes required fields

- **GIVEN** an event is written
- **WHEN** it is parsed
- **THEN** it SHALL include `event_id`, `run_id`, `created_at`, `level`, `event_type`, `surface`, `correlation_id`, `status`, and `summary` when applicable.

#### Scenario: Invalid event does not corrupt previous events

- **GIVEN** a logging attempt fails
- **WHEN** a later event is written
- **THEN** previously written JSONL lines SHALL remain parseable
- **AND** the later event SHALL be written if possible.

---

### Requirement: Audit, command, trace, app, and error logs shall be separated

OpenStock SHALL write different event families to separate files.

#### Scenario: Audit events are written to audit file

- **GIVEN** a meaningful user or system activity occurs
- **WHEN** an audit event is emitted
- **THEN** the event SHALL be written to `audit.jsonl`.

#### Scenario: Command events are written to command file

- **GIVEN** a command starts, succeeds, or fails
- **WHEN** a command event is emitted
- **THEN** the event SHALL be written to `commands.jsonl`.

#### Scenario: Trace events are written to trace file

- **GIVEN** a workflow, tool, or pipeline step changes state
- **WHEN** a trace event is emitted
- **THEN** the event SHALL be written to `trace.jsonl`.

#### Scenario: Error events are written to error file

- **GIVEN** an exception, warning, validation failure, or degraded behavior is captured
- **WHEN** an error event is emitted
- **THEN** the event SHALL be written to `errors.jsonl`.

#### Scenario: App lifecycle events are written to app file

- **GIVEN** low-level app lifecycle information is logged
- **WHEN** an app log event is emitted
- **THEN** the event SHALL be written to `app.jsonl`.

---

### Requirement: Events shall use correlation IDs

Related events SHALL share a correlation ID so an AI agent can reconstruct a workflow.

#### Scenario: CLI command events share correlation

- **GIVEN** a CLI command runs
- **WHEN** it emits command, audit, trace, and error events
- **THEN** all events for that command SHALL share the same `correlation_id`.

#### Scenario: Chat turn events share correlation

- **GIVEN** a ChatController turn starts
- **WHEN** it creates prompt, plan, tool, answer, refusal, trace, or error events
- **THEN** all events for that turn SHALL share the same `correlation_id`.

#### Scenario: Pipeline step has parent correlation

- **GIVEN** a pipeline run starts
- **WHEN** a pipeline step runs
- **THEN** the step SHALL have its own span or step identifier
- **AND** SHALL remain linked to the parent pipeline correlation ID.

---

### Requirement: Logging shall be redacted by default

OpenStock SHALL avoid writing sensitive runtime values unless explicitly configured.

#### Scenario: Default content mode is safe

- **GIVEN** no content logging override is set
- **WHEN** prompt, answer, command output, environment metadata, or tool output is logged
- **THEN** OpenStock SHALL log only metadata or redacted content.

#### Scenario: Full content requires explicit opt-in

- **GIVEN** full content logging is required for local debugging
- **WHEN** the user enables the explicit full-content mode
- **THEN** OpenStock MAY write full content
- **AND** SHALL mark events with `redaction_status` or equivalent.

#### Scenario: Redaction runs before file write

- **GIVEN** an event contains values requiring redaction
- **WHEN** the event is written
- **THEN** redaction SHALL occur before the JSONL line is persisted.

---

### Requirement: Errors and warnings shall be captured for development handoff

Errors and warnings SHALL be logged in a way that helps an AI agent investigate the failure.

#### Scenario: Exception is captured

- **GIVEN** a Python exception occurs in an instrumented path
- **WHEN** it is caught or propagated
- **THEN** OpenStock SHALL write an error event with type, message, module, function, stack trace, stack trace hash, and correlation ID where available.

#### Scenario: Swallowed exception is still logged

- **GIVEN** a best-effort path catches an exception to avoid crashing the TUI or CLI
- **WHEN** the exception is swallowed
- **THEN** OpenStock SHALL still write an error event.

#### Scenario: Warning is captured

- **GIVEN** a workflow proceeds with degraded behavior, skipped validation, stale data, missing data, or fallback behavior
- **WHEN** the warning is known
- **THEN** OpenStock SHALL write a warning event.

---

### Requirement: ChatController shall emit file logs

ChatController SHALL emit structured file logs for chat and plan lifecycle events.

#### Scenario: Natural-language turn is logged

- **GIVEN** a user submits a natural-language prompt
- **WHEN** ChatController handles the turn
- **THEN** it SHALL write `CHAT_TURN_STARTED`
- **AND** SHALL later write a completion, refusal, or error event.

#### Scenario: Plan lifecycle is logged

- **GIVEN** ChatController creates, approves, or cancels a plan
- **WHEN** the plan state changes
- **THEN** OpenStock SHALL write plan lifecycle events with the chat session ID and correlation ID.

#### Scenario: Chat runtime error is logged

- **GIVEN** a chat turn fails
- **WHEN** the error is rendered or handled
- **THEN** OpenStock SHALL write an error event in `errors.jsonl`.

---

### Requirement: CommandExecutor and tool execution shall emit file logs

Command and tool execution SHALL be logged independently of the UI surface.

#### Scenario: CommandExecutor logs command result

- **GIVEN** a command is executed through CommandExecutor
- **WHEN** it succeeds or fails
- **THEN** OpenStock SHALL write command and audit events with status and duration.

#### Scenario: Tool execution logs trace lifecycle

- **GIVEN** a tool call starts
- **WHEN** it succeeds, fails, or is refused
- **THEN** OpenStock SHALL write trace and audit events with tool name, status, duration, and correlation ID.

#### Scenario: Tool output respects content mode

- **GIVEN** a tool returns output
- **WHEN** the output is logged
- **THEN** the logged content SHALL follow the configured content logging mode.

---

### Requirement: Pipeline, verify, and backup scripts shall emit file logs

Operational shell scripts SHALL produce AI-readable log events.

#### Scenario: Pipeline run logs step lifecycle

- **GIVEN** `openstock-run-pipeline` runs
- **WHEN** each step starts, succeeds, or fails
- **THEN** the script SHALL write JSONL events with command text, status, duration, and output tail when available.

#### Scenario: Verify run logs checks

- **GIVEN** `openstock-verify` runs
- **WHEN** each check passes, warns, skips, or fails
- **THEN** the script SHALL write verify events.

#### Scenario: Backup run logs result

- **GIVEN** `openstock-backup-warehouse` runs
- **WHEN** backup succeeds or fails
- **THEN** the script SHALL write backup events.

---

### Requirement: AI-agent summary shall be generated

Each run SHALL produce or update a markdown summary optimized for AI agent review.

#### Scenario: Summary includes run overview

- **GIVEN** a run has events
- **WHEN** the summary is generated
- **THEN** `ai-agent-summary.md` SHALL include run metadata, result status, and a concise narrative of what happened.

#### Scenario: Summary lists failures

- **GIVEN** a run contains errors, warnings, or failed commands
- **WHEN** the summary is generated
- **THEN** those items SHALL be listed with references to raw log files.

#### Scenario: Summary separates fact from inference

- **GIVEN** the summary includes likely causes or suggested investigation steps
- **WHEN** those sections are written
- **THEN** they SHALL be labeled as likely or suggested rather than confirmed fact.

---

### Requirement: Logs command group shall support agent handoff

OpenStock SHALL provide a user-facing way to locate, inspect, summarize, and bundle logs.

#### Scenario: Latest logs are discoverable

- **GIVEN** at least one run exists
- **WHEN** the user runs `vnalpha logs latest` or equivalent
- **THEN** the command SHALL print the latest run path.

#### Scenario: Errors can be listed

- **GIVEN** a run contains error events
- **WHEN** the user runs `vnalpha logs errors --latest` or equivalent
- **THEN** the command SHALL show recent errors and warnings.

#### Scenario: Logs can be bundled

- **GIVEN** a latest run exists
- **WHEN** the user runs `vnalpha logs bundle --latest` or equivalent
- **THEN** OpenStock SHALL produce a portable support artifact containing summary, JSONL logs, schemas, and environment summary.

#### Scenario: Summary can be regenerated

- **GIVEN** JSONL logs exist for a run
- **WHEN** the user runs `vnalpha logs summarize --latest` or equivalent
- **THEN** `ai-agent-summary.md` SHALL be regenerated from raw events.

---

### Requirement: Observability implementation shall be tested

The logging system SHALL have automated test coverage.

#### Scenario: JSONL sink test passes

- **GIVEN** test events are written
- **WHEN** the test reads the files
- **THEN** every line SHALL parse as JSON.

#### Scenario: Redaction test passes

- **GIVEN** sensitive-looking test values are logged
- **WHEN** the files are read
- **THEN** the unsafe raw values SHALL not appear in default mode.

#### Scenario: Correlation test passes

- **GIVEN** a workflow emits multiple event types
- **WHEN** those events are read
- **THEN** related events SHALL share the expected correlation ID.

#### Scenario: Bundle test passes

- **GIVEN** a run contains logs and summary
- **WHEN** a bundle is created
- **THEN** the bundle SHALL include required files and exclude unsafe files by default.
