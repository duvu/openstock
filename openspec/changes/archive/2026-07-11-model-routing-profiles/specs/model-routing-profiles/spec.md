# Specification: Model routing profiles

## ADDED Requirements

### Requirement: Named model profiles shall be configurable

The system SHALL support provider-agnostic `small`, `default`, `reasoning`, and `long_context` profiles.

#### Scenario: Preferred environment variables resolve profiles

- **GIVEN** `VNALPHA_MODEL_SMALL`, `VNALPHA_MODEL_DEFAULT`, `VNALPHA_MODEL_REASONING`, and `VNALPHA_MODEL_LONG_CONTEXT` are configured
- **WHEN** model routing config is loaded
- **THEN** each profile SHALL resolve to its configured model ID.

#### Scenario: Legacy environment variables remain compatible

- **GIVEN** only `VNALPHA_LLM_MODEL` is configured
- **WHEN** model routing config is loaded
- **THEN** the default profile SHALL resolve to that model
- **AND** absent profile-specific settings SHALL safely resolve to the configured default or documented fallback model.

#### Scenario: Invalid profile configuration is rejected

- **GIVEN** a required profile resolves to an empty model ID or a fallback references an unknown profile
- **WHEN** config validation runs
- **THEN** a clear configuration error SHALL be raised.

---

### Requirement: Routing shall be deterministic by stage and task

The routing policy SHALL select profiles through deterministic code rather than LLM choice.

#### Scenario: Classification uses small profile

- **GIVEN** an intent-classification call
- **WHEN** its route is resolved
- **THEN** the selected profile SHALL be `small`, unless a higher-precedence override exists.

#### Scenario: Normal synthesis uses default profile

- **GIVEN** a normal grounded-answer synthesis call
- **WHEN** its route is resolved
- **THEN** the selected profile SHALL be `default`, unless overridden.

#### Scenario: Complex research uses reasoning profile

- **GIVEN** a deep analysis, multi-symbol comparison, shortlist, scenario, or diagnosis task
- **WHEN** its route is resolved
- **THEN** the selected profile SHALL be `reasoning`, unless overridden.

#### Scenario: Watchlist complexity promotes the route

- **GIVEN** a watchlist summary task
- **WHEN** symbol/artifact/context thresholds are small
- **THEN** the selected profile SHALL be `default`
- **WHEN** a configured complexity threshold is exceeded
- **THEN** the selected profile SHALL be `reasoning`.

#### Scenario: Workspace compaction uses long-context capability

- **GIVEN** an LLM workspace-compaction call
- **WHEN** `long_context` is explicitly configured
- **THEN** the route SHALL use `long_context`
- **OTHERWISE** it SHALL use `reasoning`.

---

### Requirement: Override precedence shall be explicit

The system SHALL support bounded profile overrides with deterministic precedence.

#### Scenario: Per-call override has highest precedence

- **GIVEN** a per-call profile and session/workspace overrides
- **WHEN** the route is resolved
- **THEN** the per-call profile SHALL be selected.

#### Scenario: Session override wins over workspace override

- **GIVEN** both session and workspace overrides exist
- **WHEN** a call has no per-call profile
- **THEN** the session override SHALL be selected.

#### Scenario: Workspace override persists

- **GIVEN** the user runs `/model use reasoning` with workspace scope
- **WHEN** a later gateway instance resolves the active workspace override
- **THEN** it SHALL select `reasoning` until reset or replaced.

#### Scenario: Reset restores policy

- **GIVEN** an active override
- **WHEN** `/model reset` is executed for the applicable scope
- **THEN** the override SHALL be removed
- **AND** subsequent calls SHALL return to stage/task policy.

#### Scenario: Arbitrary model IDs are not accepted as profiles

- **GIVEN** the user attempts `/model use provider/arbitrary-model`
- **WHEN** the command is validated
- **THEN** it SHALL be rejected unless a separately documented raw-override feature is explicitly enabled.

---

### Requirement: Gateway calls shall use the resolved model

The production gateway SHALL resolve a route before sending an HTTP request.

#### Scenario: Selected model ID is sent

- **GIVEN** a route resolves to `reasoning-model`
- **WHEN** the gateway creates its HTTP payload
- **THEN** the payload `model` field SHALL be `reasoning-model`.

#### Scenario: Legacy calls remain valid

- **GIVEN** existing code calls `chat(messages)` without routing metadata
- **WHEN** the gateway resolves the route
- **THEN** it SHALL use the default profile and retain the existing return shape.

#### Scenario: Successful route is returned with usage

- **GIVEN** a routed model call succeeds
- **WHEN** the gateway returns
- **THEN** usage metadata SHALL include the actual successful profile/model route.

#### Scenario: Actual model is persisted in trace

- **GIVEN** a fallback model succeeds
- **WHEN** the LLM trace is finalized
- **THEN** the trace model SHALL be updated to the actual successful model ID where routed usage is available.

---

### Requirement: Model fallback shall be explicit and configurable

The gateway SHALL use a configured ordered profile fallback chain for retryable route failures.

#### Scenario: Reasoning falls back to default

- **GIVEN** the reasoning model is unavailable
- **AND** the reasoning fallback chain begins with `default`
- **WHEN** the reasoning route fails with a fallback-eligible provider/model error
- **THEN** the gateway SHALL try the default profile.

#### Scenario: Duplicate model IDs are skipped

- **GIVEN** two profiles resolve to the same model ID
- **WHEN** fallback decisions are generated
- **THEN** that model ID SHALL not be called twice.

#### Scenario: Authentication errors do not silently fallback

- **GIVEN** the provider rejects authentication or authorization
- **WHEN** the HTTP failure is classified as non-retryable
- **THEN** the gateway SHALL raise the error without silently trying weaker profiles.

#### Scenario: Fallback exhaustion is reported

- **GIVEN** every selected/fallback route fails
- **WHEN** the chain is exhausted
- **THEN** a clear gateway error SHALL be returned.

---

### Requirement: Assistant stages shall supply routing metadata

Assistant components SHALL identify their stage and relevant task complexity.

#### Scenario: Classifier supplies intent task type

- **GIVEN** intent classification requires an LLM call
- **WHEN** the classifier invokes the gateway
- **THEN** it SHALL pass `stage=classify` and `task_type=intent_classification`.

#### Scenario: Invalid small-model classifier JSON retries stronger profile

- **GIVEN** the small-profile classifier response is invalid JSON
- **WHEN** classifier parsing fails
- **THEN** it SHALL retry once with an explicit `default` profile
- **AND** SHALL fail clearly if the retry remains invalid.

#### Scenario: Synthesizer supplies task complexity

- **GIVEN** a plan and tool outputs
- **WHEN** the synthesizer invokes the gateway
- **THEN** it SHALL pass the mapped task type and bounded complexity metadata.

---

### Requirement: Workspace compaction shall support a routed LLM path

Deterministic compaction SHALL remain the safe default, while an explicit LLM path MAY use model routing.

#### Scenario: Default compaction remains deterministic

- **GIVEN** `/context compact` is executed without `--llm`
- **WHEN** compaction runs
- **THEN** no LLM call SHALL be required.

#### Scenario: Explicit LLM compaction is routed

- **GIVEN** `/context compact --llm` or an injected LLM client
- **WHEN** compaction invokes the gateway
- **THEN** it SHALL pass `stage=compact` and `task_type=workspace_compaction`.

#### Scenario: LLM compaction failure preserves a usable result

- **GIVEN** the routed compaction call fails
- **WHEN** compaction completes
- **THEN** the deterministic summary SHALL be written
- **AND** the result SHALL contain a warning.

---

### Requirement: Users shall manage routing through slash commands

The shared command registry SHALL expose model-profile management.

#### Scenario: Model status is available

- **GIVEN** the user executes `/model status`
- **THEN** the result SHALL show active override, resolved models, fallback policy, and latest route when available.

#### Scenario: Model profiles are listed

- **GIVEN** the user executes `/model profiles` or `/models`
- **THEN** configured profiles, resolved model IDs, provider labels, and fallback chains SHALL be shown.

#### Scenario: User selects a profile

- **GIVEN** a configured profile name
- **WHEN** the user executes `/model use <profile>`
- **THEN** the session/workspace override SHALL be updated according to scope.

#### Scenario: Route can be explained without making a model call

- **GIVEN** a stage or task name
- **WHEN** the user executes `/model explain-route <stage-or-task>`
- **THEN** a deterministic route decision SHALL be returned without invoking the LLM provider.

---

### Requirement: Model routing shall be observable without logging prompts

Every routed gateway lifecycle SHALL emit best-effort structured audit events.

#### Scenario: Route selection is logged

- **GIVEN** a gateway route is resolved
- **WHEN** the call begins
- **THEN** `MODEL_ROUTE_SELECTED` and `MODEL_CALL_STARTED` SHALL be emitted.

#### Scenario: Successful usage is logged

- **GIVEN** a model call succeeds
- **WHEN** usage metadata is available
- **THEN** `MODEL_CALL_SUCCEEDED` SHALL include profile/model, latency, tokens, and estimated cost when supplied.

#### Scenario: Failure and fallback are logged

- **GIVEN** a model call fails and fallback is used
- **WHEN** the gateway advances routes
- **THEN** `MODEL_CALL_FAILED` and `MODEL_FALLBACK_USED` SHALL be emitted.

#### Scenario: Prompt content is excluded

- **GIVEN** route metadata contains prompt/content fields
- **WHEN** observability metadata is redacted
- **THEN** raw prompt and response content SHALL NOT appear in model-route events.

---

### Requirement: Tests and documentation shall prove the routing contract

The implementation SHALL include focused tests and operator documentation.

#### Scenario: Focused tests exist

- **GIVEN** repository tests are inspected
- **THEN** they SHALL cover config, routing, overrides, fallback, gateway payload, classifier recovery, commands, observability, and compaction.

#### Scenario: Documentation exists

- **GIVEN** repository docs are inspected
- **THEN** `vnalpha/docs/model-routing-profiles.md` SHALL document profiles, configuration, routing, overrides, fallback, commands, observability, and operational recommendations.

#### Scenario: Validation evidence is recorded

- **GIVEN** implementation validation commands are executed
- **WHEN** the OpenSpec is reviewed for completion
- **THEN** `validation.md` SHALL record command outcomes and any unresolved exceptions.
