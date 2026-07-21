## ADDED Requirements

### Requirement: Queue health SHALL gate job claims
The system SHALL expose queue schema, runtime settings, integrity, file/WAL size, disk state, queue depth, oldest age and lease status.

#### Scenario: Queue integrity validation fails
- **WHEN** the queue health gate reports unsupported schema or failed integrity
- **THEN** the worker does not claim new jobs
- **AND** the system returns an actionable operator result
- **AND** does not delete or recreate the queue automatically.

### Requirement: Queue retention SHALL be bounded and evidence-aware
Active jobs SHALL never be pruned. Terminal details MAY be pruned only after retained maintenance evidence is preserved.

#### Scenario: A terminal job is referenced by a retained maintenance run
- **WHEN** the job reaches the configured retention boundary
- **THEN** a bounded terminal summary is preserved in the run ledger or the queue row remains retained
- **AND** historical status distinguishes pruned detail from an unknown job ID.

### Requirement: Queue checkpoint and storage failures SHALL be explicit

#### Scenario: Queue storage becomes read-only or full
- **WHEN** SQLite cannot persist a queue update
- **THEN** the operation returns a typed storage failure
- **AND** prior committed state remains intact
- **AND** the system does not report the requested update as successful.

### Requirement: Queue migration and recovery SHALL be non-destructive

#### Scenario: A queue schema migration cannot complete
- **WHEN** package or operator migration fails
- **THEN** the prior queue is preserved for recovery
- **AND** the system does not replace it with an empty queue.

### Requirement: The supported package SHALL install one queue runtime
The package SHALL create queue and lock paths with documented ownership, install exactly one provisioner daemon and install a maintenance producer timer disabled by default.

#### Scenario: The supported package starts the runtime
- **WHEN** the operator enables the provisioner
- **THEN** exactly one packaged service claims queue jobs
- **AND** it uses the configured queue, warehouse and global lock paths.

### Requirement: Backup and restore SHALL cover both state stores

#### Scenario: An operator performs a supported backup
- **WHEN** the provisioner reaches a safe boundary
- **THEN** the procedure checkpoints the queue
- **AND** captures DuckDB, SQLite queue state and required configuration/permissions
- **AND** restore runs health and compatibility checks before restarting work.

### Requirement: Architecture documentation SHALL match the runtime
Canonical architecture, data-pipeline, deployment, CLI/TUI help and operator documentation SHALL describe the local SQLite queue, one long-running provisioner, one DuckDB writer, wait policies and session finalization.

#### Scenario: Repository consistency validation runs
- **WHEN** canonical documentation presents a one-shot provisioner or direct multi-step maintenance as the normal path
- **THEN** the consistency check fails.

### Requirement: Live proof SHALL cover ten consecutive sessions

#### Scenario: Program completion is evaluated
- **WHEN** implementation tests pass but the ten-session installed-host evidence is absent
- **THEN** the queue-runtime program remains incomplete
- **AND** no production-readiness conclusion is recorded.

#### Scenario: Live proof is collected
- **WHEN** each session completes
- **THEN** evidence links the maintenance run, expected acquisition jobs, finalization job, queue health, incremental ranges, duplicate checks and research result status.
