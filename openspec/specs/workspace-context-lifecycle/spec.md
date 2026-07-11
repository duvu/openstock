# workspace-context-lifecycle Specification

## Purpose
TBD - created by archiving change workspace-context-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Workspace context shall be persisted to files

The system SHALL persist curated workspace context to a file-backed workspace directory.

#### Scenario: First workspace is created

- **GIVEN** no workspace exists
- **WHEN** TUI or workspace command initializes workspace context
- **THEN** a new workspace directory SHALL be created
- **AND** `workspace.json`, `context.md`, `events.jsonl`, `artifacts/`, `archive/`, and `exports/` SHALL exist.

#### Scenario: Latest workspace pointer is updated

- **GIVEN** a workspace is created or resumed
- **WHEN** latest workspace changes
- **THEN** `latest.json` SHALL point to the active workspace id.

#### Scenario: Workspace writes are atomic

- **GIVEN** workspace state is written
- **WHEN** the write succeeds
- **THEN** readers SHALL see either the previous complete state or the new complete state, not a partial file.

---

### Requirement: Workspace state shall be distinct from audit logs

Workspace context SHALL be curated working state and SHALL NOT replace immutable audit logs.

#### Scenario: Cleaning context does not delete audit logs

- **GIVEN** audit logs exist
- **WHEN** `/context clean` runs
- **THEN** audit logs SHALL remain untouched.

#### Scenario: Context files reference source artifacts

- **GIVEN** compact or context files summarize prior work
- **WHEN** they include findings
- **THEN** they SHOULD include local source references where feasible.

---

### Requirement: Context status command shall report workspace health

The system SHALL support `/context status`.

#### Scenario: Status reports active workspace

- **GIVEN** an active workspace exists
- **WHEN** user runs `/context status`
- **THEN** the result SHALL include workspace id, title, mode, active date, active symbols, last updated time, last compacted time, context size, open tasks, warnings, errors, and suggested action.

#### Scenario: Status recommends compaction

- **GIVEN** workspace context exceeds configured size or age thresholds
- **WHEN** `/context status` runs
- **THEN** the result SHALL recommend `/context compact`.

---

### Requirement: Context compaction shall produce compact summary

The system SHALL support `/context compact`.

#### Scenario: Compact writes compact.md

- **GIVEN** an active workspace exists
- **WHEN** user runs `/context compact`
- **THEN** `compact.md` SHALL be written or updated.

#### Scenario: Compact preserves important state

- **GIVEN** workspace contains active symbols, active date, findings, assumptions, decisions, open tasks, warnings, and artifact refs
- **WHEN** compaction runs
- **THEN** compact summary SHALL preserve those items.

#### Scenario: Compact de-emphasizes noisy context

- **GIVEN** workspace contains duplicate outputs, repeated traces, resolved transient errors, or large tables stored elsewhere
- **WHEN** compaction runs
- **THEN** compact summary SHALL avoid copying those noisy details verbatim.

---

### Requirement: Context cleaning shall be safe by default

The system SHALL support `/context clean` with dry-run and archive-first behavior.

#### Scenario: Default clean is dry-run

- **GIVEN** active workspace contains cleanable items
- **WHEN** user runs `/context clean` without destructive flags
- **THEN** the system SHALL return a clean plan
- **AND** SHALL NOT delete or archive files.

#### Scenario: Clean archives before removal

- **GIVEN** user runs clean with archive-first behavior
- **WHEN** clean removes noisy workspace items
- **THEN** items SHALL be archived before removal when feasible.

#### Scenario: Protected files are not cleaned

- **GIVEN** workspace contains `workspace.json`, `compact.md`, audit logs, pinned items, or user-authored notes
- **WHEN** clean runs
- **THEN** protected items SHALL NOT be deleted.

---

### Requirement: New workspace command shall start a clean workspace safely

The system SHALL support `/context new`.

#### Scenario: New workspace compacts current workspace first

- **GIVEN** an active workspace exists
- **WHEN** user runs `/context new`
- **THEN** the current workspace SHALL be compacted unless `--no-compact` is provided.

#### Scenario: New workspace archives previous workspace

- **GIVEN** current workspace exists
- **WHEN** new workspace is created
- **THEN** previous workspace SHALL be marked inactive or archived
- **AND** latest pointer SHALL move to the new workspace.

#### Scenario: New workspace does not delete audit logs

- **GIVEN** audit logs exist for previous workspace activity
- **WHEN** `/context new` runs
- **THEN** audit logs SHALL remain untouched.

---

### Requirement: Resume command shall load previous workspace

The system SHALL support `/context resume` and `/context list`.

#### Scenario: Resume latest workspace

- **GIVEN** at least one workspace exists
- **WHEN** user runs `/context resume`
- **THEN** the latest workspace SHALL be loaded
- **AND** a resume summary SHALL be shown.

#### Scenario: Resume workspace by id

- **GIVEN** workspace `<workspace-id>` exists
- **WHEN** user runs `/context resume <workspace-id>`
- **THEN** that workspace SHALL be loaded
- **AND** latest pointer SHALL be updated.

#### Scenario: List workspaces

- **GIVEN** multiple workspaces exist
- **WHEN** user runs `/context list`
- **THEN** the system SHALL list workspace ids, titles, modes, statuses, and updated times.

---

### Requirement: Export command shall create context bundle

The system SHALL support `/context export`.

#### Scenario: Export creates bundle

- **GIVEN** an active workspace exists
- **WHEN** user runs `/context export`
- **THEN** a bundle directory SHALL be created under workspace exports
- **AND** it SHALL include manifest, workspace state, compact summary if present, context markdown, and selected artifacts.

#### Scenario: Export includes checksums

- **GIVEN** export bundle is created
- **WHEN** manifest is inspected
- **THEN** checksums or equivalent file integrity metadata SHOULD be present.

---

### Requirement: Workspace commands shall be available from TUI composer

The TUI SHALL route workspace lifecycle commands through the single composer input.

#### Scenario: Context command renders in OutputStream

- **GIVEN** user runs `/context status`
- **WHEN** command completes
- **THEN** the result SHALL render in OutputStream.

#### Scenario: Convenience alias works

- **GIVEN** aliases are implemented
- **WHEN** user runs `/compact`
- **THEN** it SHALL behave as `/context compact`.

---

### Requirement: TUI shall show active workspace identity

The TUI SHALL show current workspace identity in compact status/header/footer UI.

#### Scenario: Startup resumes workspace

- **GIVEN** latest workspace exists
- **WHEN** TUI starts
- **THEN** it SHALL resume the latest workspace by default
- **AND** show a resume summary or status line.

#### Scenario: Workspace id is visible

- **GIVEN** TUI is running
- **WHEN** status/header/footer is rendered
- **THEN** active workspace id or title SHALL be visible.

---

### Requirement: Assistant shall use bounded workspace context

Assistant workflows SHALL use compact workspace context, not raw unbounded history.

#### Scenario: Assistant context provider loads compact summary

- **GIVEN** active workspace has `compact.md`
- **WHEN** assistant prepares a response
- **THEN** compact summary and workspace metadata MAY be injected as bounded context.

#### Scenario: Raw events are not injected by default

- **GIVEN** active workspace has large `events.jsonl`
- **WHEN** assistant prepares context
- **THEN** raw events SHALL NOT be injected by default.

#### Scenario: Stale context caveat is preserved

- **GIVEN** compact context is old or stale
- **WHEN** assistant uses it
- **THEN** stale-context metadata SHALL be available so the assistant can avoid over-trusting it.

---

### Requirement: Workspace persistence shall be redaction-aware

Workspace context SHALL avoid storing secrets or sensitive raw values.

#### Scenario: Sensitive-looking input is redacted or skipped

- **GIVEN** submitted input contains sensitive-looking token, credential, or cookie
- **WHEN** workspace records input
- **THEN** sensitive values SHALL be redacted or the raw input SHALL be skipped.

#### Scenario: Audit event avoids raw input

- **GIVEN** input is recorded
- **WHEN** audit event is emitted
- **THEN** audit metadata SHOULD prefer input kind and length over raw full input.

---

### Requirement: Workspace lifecycle shall be observable

Workspace operations SHALL emit best-effort workspace and audit events.

#### Scenario: Workspace creation is logged

- **GIVEN** a workspace is created
- **WHEN** operation succeeds
- **THEN** `WORKSPACE_CREATED` or equivalent SHALL be emitted.

#### Scenario: Compaction is logged

- **GIVEN** compaction runs
- **WHEN** operation succeeds
- **THEN** `WORKSPACE_COMPACTED` or equivalent SHALL be emitted.

#### Scenario: Clean is logged

- **GIVEN** clean runs
- **WHEN** operation completes
- **THEN** `WORKSPACE_CLEANED` or dry-run equivalent SHALL be emitted.

#### Scenario: Workspace error is logged

- **GIVEN** workspace operation fails
- **WHEN** failure is handled
- **THEN** `WORKSPACE_ERROR` or equivalent SHALL be emitted.

---

### Requirement: Documentation and tests shall prove lifecycle behavior

The implementation SHALL include docs and tests.

#### Scenario: Docs exist

- **GIVEN** implementation is complete
- **WHEN** docs are inspected
- **THEN** `vnalpha/docs/workspace-context-lifecycle.md` SHALL exist and document file layout, commands, lifecycle behavior, and safety boundaries.

#### Scenario: Lifecycle test passes

- **GIVEN** tests run
- **THEN** there SHALL be a test covering create or resume workspace, record input, compact, status, export, new workspace, and resume old workspace.

#### Scenario: Safety tests pass

- **GIVEN** tests run
- **THEN** they SHALL prove clean/new do not delete audit logs and redaction rules are applied.

