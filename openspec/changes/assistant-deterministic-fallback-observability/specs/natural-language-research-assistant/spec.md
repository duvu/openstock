## ADDED Requirements

### Requirement: Assistant SHALL preserve successful read-only tool evidence

For a completed safe read-only plan with deterministic renderable tool output, the assistant SHALL return a validated deterministic answer before treating LLM synthesis as an enhancement. Synthesis call, parse, groundedness, or policy failure SHALL return that deterministic answer with degraded metadata and a bounded public warning. Unsafe write/execution plans, failed tools, and turns without valid deterministic evidence SHALL remain fail-closed.

#### Scenario: Market regime synthesis is unavailable
- **GIVEN** `market.get_regime` completed successfully with persisted evidence
- **WHEN** synthesis gateway access fails
- **THEN** the user receives a deterministic market-regime answer with caveats
- **AND** the assistant session status is `DEGRADED_SUCCESS`.

#### Scenario: Context validation rejects model output
- **GIVEN** a read-only context tool completed successfully
- **WHEN** answer validation rejects the synthesized output
- **THEN** the user receives a validated deterministic answer
- **AND** the warning identifies answer validation as the degraded stage.
