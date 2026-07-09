# sandbox-compute Specification Delta

## ADDED Requirements

### Requirement: System shall model sandbox jobs explicitly

Generated research computation SHALL be represented as a first-class sandbox job.

#### Scenario: Sandbox job is created

- **WHEN** the assistant or user requests generated research computation
- **THEN** the system creates a sandbox job with a job ID, purpose, input dataset references, generated code, resource limits, filesystem policy, network policy, output schema, expected artifacts, and correlation ID

### Requirement: Sandbox execution shall be constrained

Sandbox jobs SHALL execute under bounded CPU, memory, runtime, network, and filesystem policies.

#### Scenario: Safe research code is executed

- **WHEN** a policy-approved sandbox job runs
- **THEN** the job has no network access
- **AND** has bounded runtime
- **AND** has bounded memory
- **AND** can read only approved research data paths
- **AND** can write only to its job output directory

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

Successful sandbox jobs SHALL produce validated, persisted research artifacts.

#### Scenario: Job succeeds with required outputs

- **WHEN** sandbox code completes successfully
- **THEN** the system validates required outputs
- **AND** persists `result.json`
- **AND** persists `summary.md`
- **AND** persists an artifact manifest
- **AND** records generated code and input dataset references

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

Natural-language requests that require generated code execution SHALL be approval-gated unless proven safe by deterministic policy.

#### Scenario: Assistant proposes generated code execution

- **WHEN** a natural-language research request requires generated code
- **THEN** the assistant previews the plan
- **AND** shows the sandbox job purpose, input dataset references, and generated code summary
- **AND** waits for explicit approval before execution

### Requirement: Sandbox observability shall be closed-loop

Sandbox lifecycle events SHALL be persisted with correlation IDs.

#### Scenario: Sandbox job completes

- **WHEN** a sandbox job reaches a terminal state
- **THEN** the system persists lifecycle events
- **AND** links artifacts, generated code, errors, and validation output to the same correlation ID
