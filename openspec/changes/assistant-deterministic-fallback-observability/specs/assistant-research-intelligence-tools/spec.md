## MODIFIED Requirements

### Requirement: Research answer audit SHALL preserve a valid answer

The assistant SHALL persist compact answer-audit metadata for deep workflows. Failure
to persist an audit, project knowledge, or finalize a session after a validated answer
exists SHALL mark available lifecycle records as degraded without suppressing that
answer. If no validated answer exists, the request SHALL remain fail-closed.

#### Scenario: A research answer is returned
- **WHEN** a research-intelligence answer passes groundedness and policy validation
- **THEN** an audit record SHALL persist intent, tools, artifact references, freshness, groundedness, policy result, caveats, assistant session ID, and correlation ID.

#### Scenario: Audit record is linked to answer
- **WHEN** audit persistence succeeds
- **THEN** `research_metadata` SHALL include `research_answer_audit_id`.

#### Scenario: Audit persistence fails after a valid answer
- **GIVEN** a validated research answer exists
- **WHEN** the audit record cannot be stored
- **THEN** the assistant SHALL return the answer with `DEGRADED_SUCCESS` metadata
- **AND** SHALL record sanitized audit-persistence failure where possible.

#### Scenario: File observability is active
- **WHEN** a research audit is persisted
- **THEN** the system SHOULD emit `RESEARCH_ANSWER_AUDITED` without copying raw prompt or full answer content into the event.
