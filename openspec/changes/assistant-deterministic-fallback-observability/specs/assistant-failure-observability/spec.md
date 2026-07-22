## ADDED Requirements

### Requirement: Assistant SHALL expose bounded downstream failure diagnostics

When a request reaches a downstream assistant lifecycle failure, CLI and TUI SHALL expose the same sanitized diagnostic fields: a finite stage selected from `CLASSIFY`, `PLAN`, `TOOL_EXECUTION`, `SYNTHESIS_CALL`, `SYNTHESIS_PARSE`, `ANSWER_VALIDATION`, `AUDIT_PERSIST`, `KNOWLEDGE_PROJECTION`, and `SESSION_FINALIZE`; a stable category; correlation ID; runtime build SHA; model route when selected; and trace ID when it exists. They SHALL NOT expose credentials, raw provider payloads, prompts, or raw exception text.

#### Scenario: Synthesis gateway fails
- **GIVEN** a safe read-only plan completed deterministic tools
- **WHEN** the synthesis gateway raises
- **THEN** the answer diagnostic reports `SYNTHESIS_CALL` with a stable category
- **AND** the visible warning includes the correlation ID.

#### Scenario: Structured response parsing fails
- **GIVEN** a safe read-only plan completed deterministic tools
- **WHEN** synthesis returns invalid structured output
- **THEN** the answer diagnostic reports `SYNTHESIS_PARSE`
- **AND** CLI and TUI render the same bounded warning contract.

#### Scenario: Optional persistence fails after a valid answer
- **GIVEN** a valid answer exists
- **WHEN** audit, knowledge projection, or session finalization fails
- **THEN** the diagnostic reports the matching finite stage
- **AND** the user receives the valid answer with a degraded warning.
