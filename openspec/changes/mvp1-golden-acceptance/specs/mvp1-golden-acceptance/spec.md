# Capability: MVP1 golden acceptance

## ADDED Requirements

### Requirement: Golden end-to-end conversation on the real code path

One automated golden conversation SHALL prove the MVP1 chat vertical slice from
an empty warehouse and empty symbol-knowledge directory, using the real planner,
provisioning, canonical/feature/scoring builders, deep analysis, synthesis,
groundedness, audit and symbol-knowledge projection, with fixture-backed data and
a fake LLM. Only the network-fetch boundary and the LLM gateway are faked.

#### Scenario: Empty warehouse to grounded answer
- **GIVEN** an empty warehouse and empty knowledge directory
- **WHEN** the user asks `Phân tích FPT`
- **THEN** provisioning visibly runs before analysis, symbols/OHLCV/VNINDEX/
  features/score are persisted, a grounded audit with as-of, evidence, freshness,
  caveats and the provisioning+analysis trace is recorded, and deterministic
  symbol knowledge is projected whose value equals the persisted score.

#### Scenario: Raw prose is not promoted
- **WHEN** knowledge is projected
- **THEN** only validated persisted evidence becomes a claim; chat/model prose
  is never a factual claim.

### Requirement: Fresh reuse, explicit refresh and shared contract

#### Scenario: Follow-up reuses without new provider fetches
- **GIVEN** a first analysis already provisioned
- **WHEN** a follow-up question is asked
- **THEN** no new provider fetch occurs and projection stays idempotent.

#### Scenario: Explicit refresh performs bounded disclosed work
- **WHEN** an explicit refresh runs
- **THEN** force-refresh is threaded and the bounded actions taken are disclosed.

#### Scenario: Slash and natural language share the operation
- **WHEN** the shared `ensure_current_symbol_ready` operation `/analyze` uses is
  invoked after the NL turn
- **THEN** it reuses the same persisted evidence with no new fetch.

### Requirement: Failure fails closed and preserves state

#### Scenario: Service-unavailable fails closed
- **GIVEN** a service-unavailable provisioning fixture
- **WHEN** provisioning runs
- **THEN** it returns an actionable typed failure and promotes no partial or
  corrupt analysis evidence or memory claim.
