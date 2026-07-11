# sandbox-compute Specification Delta

## ADDED Requirements

### Requirement: System shall model sandbox jobs explicitly

Generated research computation SHALL be represented as a first-class sandbox job.

#### Scenario: Sandbox job is created

- **WHEN** the assistant or user requests generated research computation
- **THEN** the system creates a sandbox job with a job ID, purpose, input dataset references, generated code, resource limits, filesystem policy, network policy, output schema, expected artifacts, and correlation ID

### Requirement: Sandbox execution shall use a fail-closed Linux Docker boundary

Sandbox jobs SHALL execute only through Docker Engine on a supported Linux host. Docker Engine availability and Linux-host compatibility SHALL pass preflight before execution. If Docker Engine is unavailable, the host is unsupported, or preflight fails, the system SHALL reject the job, persist rejection evidence, and SHALL NOT execute generated code through a local interpreter or another fallback runtime.

#### Scenario: Safe research code is executed in a hardened container

- **WHEN** a policy-approved sandbox job runs
- **THEN** it runs in Docker OS isolation from an immutable, prebuilt image referenced by digest
- **AND** the runtime does not build, pull, or select a mutable image tag at job execution
- **AND** the container has no network access through `--network none`
- **AND** the container root filesystem is read-only
- **AND** approved research input paths are mounted read-only
- **AND** the canonical job output directory is the sole writable mount
- **AND** the process runs as a non-root user
- **AND** Linux capabilities are dropped unless a documented minimum exception is required
- **AND** PID count is bounded
- **AND** has bounded runtime
- **AND** has bounded memory
- **AND** has bounded CPU

#### Scenario: Docker preflight cannot establish the execution boundary

- **WHEN** Docker Engine is unavailable, the host is not supported Linux, or Docker preflight fails
- **THEN** the system rejects the sandbox job before generated code execution
- **AND** does not fall back to local-process execution or another runtime
- **AND** persists the failed preflight and rejection evidence with the correlation ID

### Requirement: Sandbox controls shall be defense in depth

Docker OS isolation SHALL be the primary generated-code execution boundary. Policy checks, static guards, output validation, and artifact validation SHALL be defense-in-depth controls and SHALL NOT be treated as substitutes for Docker isolation.

### Requirement: Sandbox code shall pass static guard before execution

Generated code SHALL be rejected before execution if it contains dangerous imports, dangerous patterns, or trading-execution references.

#### Scenario: Code imports network library

- **WHEN** generated code imports `requests`, `httpx`, `urllib`, or uses socket/network APIs
- **THEN** the static guard rejects the job
- **AND** no code is executed
- **AND** `SANDBOX_GUARD_REJECTED` is emitted

#### Scenario: Code attempts shell execution

- **WHEN** generated code uses shell execution patterns
- **THEN** the static guard rejects the job
- **AND** no code is executed

#### Scenario: Code references trading execution

- **WHEN** generated code references broker, order, account, portfolio, margin, allocation, transfer, or trading execution behavior
- **THEN** the static guard rejects the job
- **AND** the system preserves the read-only research boundary

### Requirement: Sandbox outputs shall be validated and persisted

Successful sandbox jobs SHALL produce validated, persisted research artifacts in the canonical job layout `logs/runs/<run-id>/sandbox/<job-id>/`.

#### Scenario: Job succeeds with required outputs

- **WHEN** sandbox code completes successfully
- **THEN** the system validates required outputs
- **AND** persists `result.json`
- **AND** persists `summary.md`
- **AND** persists an artifact manifest
- **AND** records generated code and input dataset references
- **AND** persists the job request metadata, generated code, input dataset references or snapshots, stdout, stderr, guard result, execution result, validation result, artifact manifest, and lifecycle-event evidence
- **AND** records the image digest, Docker preflight result, effective resource limits, mount policy, network policy, container security controls, generated-code hash, and correlation ID

#### Scenario: Required output is missing

- **WHEN** sandbox code exits successfully but does not produce required outputs
- **THEN** the system marks the job as failed
- **AND** captures validation failure evidence

### Requirement: TUI shall expose sandbox commands

The default composer path SHALL expose sandbox operations.

#### Scenario: Sandbox run is submitted

- **WHEN** the user submits `/sandbox run <purpose>`
- **THEN** the TUI creates or routes a sandbox job
- **AND** renders job status inline
- **AND** emits command lifecycle events

#### Scenario: Sandbox status is requested

- **WHEN** the user submits `/sandbox status <job-id>`
- **THEN** the TUI renders the current job status inline

#### Scenario: Sandbox artifact is requested

- **WHEN** the user submits `/sandbox artifact <job-id>`
- **THEN** the TUI renders artifact metadata and paths inline

### Requirement: Assistant sandbox execution shall require approval

Every generated-code execution requested through natural language or sandbox commands SHALL require explicit user approval. Deterministic, bounded, read-only, or policy-safe characteristics SHALL NOT bypass approval.

#### Scenario: Assistant proposes generated code execution

- **WHEN** a natural-language research request requires generated code
- **THEN** the assistant previews the plan
- **AND** shows the sandbox job purpose, input dataset references, and generated code summary
- **AND** waits for explicit approval before execution

#### Scenario: Generated-code execution has not received approval

- **WHEN** a generated-code sandbox job lacks explicit user approval
- **THEN** the system does not execute the job
- **AND** records the approval-gate rejection or pending state with the correlation ID

### Requirement: Sandbox observability shall be closed-loop

Sandbox lifecycle events SHALL be persisted with correlation IDs.

#### Scenario: Sandbox job completes

- **WHEN** a sandbox job reaches a terminal state
- **THEN** the system persists lifecycle events
- **AND** links artifacts, generated code, errors, and validation output to the same correlation ID
