# Specification: Assistant Research Intelligence Tools

## ADDED Requirements

### Requirement: Expanded research-intelligence intents

The assistant SHALL classify and plan bounded research-intelligence workflows.

#### Scenario: User asks for deep symbol review

- **WHEN** the user asks for a full research review of a symbol
- **THEN** the assistant SHALL classify `deep_analyze_symbol`
- **AND** SHALL plan `analysis.deep_symbol` deterministically.

#### Scenario: User asks for market or sector context

- **WHEN** the user asks for persisted market-regime or sector-strength context
- **THEN** the assistant SHALL classify `review_market_regime` or `review_sector_strength`
- **AND** SHALL plan the corresponding read-only context tool.

#### Scenario: User asks for deep watchlist synthesis

- **WHEN** the user asks for setup distribution, sector clusters, quality, risks, or a research agenda across the watchlist
- **THEN** the assistant SHALL classify `summarize_watchlist_deep`
- **AND** SHALL plan `watchlist.summarize_deep`.

#### Scenario: User asks for shortlist, scenario, or setup evidence

- **WHEN** the user asks for research prioritization, conditional scenario context, or historical setup evidence
- **THEN** the assistant SHALL classify the corresponding bounded intent
- **AND** SHALL use deterministic tool planning.

---

### Requirement: Deterministic tool grounding

The assistant SHALL use bounded deterministic tools for research intelligence.

#### Scenario: Assistant answers sector context

- **WHEN** the answer discusses sector strength
- **THEN** the answer SHALL be grounded in `sector.get_strength` or equivalent structured output.

#### Scenario: Assistant performs deep symbol analysis

- **WHEN** a deep symbol plan executes
- **THEN** score, feature, level, market, sector, freshness, quality, and lineage context SHALL come from bounded persisted-data tools
- **AND** the model SHALL receive no raw SQL, filesystem, network, or unrestricted-code capability.

#### Scenario: Assistant prepares shortlist or scenario context

- **WHEN** shortlist or scenario tools execute
- **THEN** they SHALL return structured payloads containing methodology or conditions, freshness, artifact references, missing data, and caveats.

#### Scenario: Unsafe tool is inserted into a plan

- **WHEN** a plan contains a tool not approved by the central assistant tool policy
- **THEN** planner or executor validation SHALL reject it before execution.

---

### Requirement: Research tool payloads shall be validated before synthesis

The assistant SHALL validate deterministic research payloads before invoking the answer model.

#### Scenario: Planned tool output is missing

- **WHEN** one or more planned research tool outputs are absent
- **THEN** synthesis SHALL fail before an LLM call.

#### Scenario: Complete payload violates required field contract

- **WHEN** a research payload claims availability but omits required intent-template fields
- **THEN** synthesis SHALL fail closed.

#### Scenario: Partial payload discloses missing data

- **WHEN** a structured payload explicitly lists missing upstream artifacts
- **THEN** synthesis MAY continue
- **AND** final-answer validation SHALL require those missing artifacts to be disclosed.

---

### Requirement: Intent-specific synthesis templates

Each research intent SHALL have a synthesis template.

#### Scenario: Research synthesis starts

- **WHEN** a research-intelligence answer is synthesized
- **THEN** the model context SHALL include required fields, allowed framing, required caveats, and the missing-data rule for that intent.

#### Scenario: Source-reference vocabulary is supplied

- **WHEN** synthesis context is assembled
- **THEN** it SHALL include a bounded list of valid tool, step, and artifact references
- **AND** the model SHALL be instructed to use only those references.

#### Scenario: Model omits source references

- **WHEN** the model returns no `grounded_source_refs`
- **THEN** the runtime MAY attach only references derived deterministically from the executed plan and tool payloads.

---

### Requirement: Research-only policy check

The assistant SHALL reject or rewrite execution-oriented outputs.

#### Scenario: User asks for shortlist as execution list

- **WHEN** a prompt implies broker, account, allocation, margin, order placement, or autonomous execution
- **THEN** the assistant SHALL refuse or reframe the request into research-only output.

#### Scenario: Shortlist or scenario answer lacks research framing

- **WHEN** a shortlist or scenario answer omits an explicit research-only or not-a-recommendation disclaimer
- **THEN** the answer SHALL NOT be returned unchanged
- **AND** SHALL be rewritten through a deterministic research-only fallback or fail closed.

#### Scenario: Model output contains execution-oriented wording

- **WHEN** final-answer policy validation detects prohibited wording
- **THEN** the assistant SHALL rewrite from structured tool payloads or fail closed.

---

### Requirement: Groundedness validation

The assistant SHALL validate final research answers against tool outputs.

#### Scenario: Synthesis references a metric

- **WHEN** the answer cites a score, rank, setup, regime, sector, level, sample size, return, or evidence metric
- **THEN** the metric SHALL exist in the structured tool payload or be explicitly marked unavailable.

#### Scenario: Synthesis references a source

- **WHEN** the answer supplies a grounded source reference
- **THEN** the reference SHALL match an executed tool, plan step, or artifact reference from the tool payloads.

#### Scenario: Tool payload reports missing data

- **WHEN** one or more research tool payloads list missing data
- **THEN** the answer SHALL disclose those items in summary, basis, caveats, or `missing_data`.

#### Scenario: Basis or caveats are empty

- **WHEN** a research answer lacks basis or risks/caveats
- **THEN** groundedness validation SHALL fail.

---

### Requirement: Deterministic fail-closed fallback

The system SHALL preserve a usable research answer when safe structured evidence exists but model synthesis is unavailable or invalid.

#### Scenario: Model call or JSON parsing fails

- **WHEN** a research synthesis call fails or returns invalid JSON
- **THEN** the system SHALL build a deterministic answer from structured tool payloads
- **AND** SHALL validate that fallback before returning it.

#### Scenario: Model answer is ungrounded

- **WHEN** source, metric, missing-data, or policy validation fails
- **THEN** the system SHALL build and validate a deterministic fallback.

#### Scenario: Deterministic fallback also fails

- **WHEN** the fallback cannot pass groundedness and policy validation
- **THEN** the request SHALL fail with a synthesis error
- **AND** SHALL NOT return an unvalidated answer.

---

### Requirement: Research answer audit

The assistant SHALL persist compact answer-audit metadata for deep workflows.

#### Scenario: A research answer is returned

- **WHEN** a research-intelligence answer passes groundedness and policy validation
- **THEN** an audit record SHALL persist intent, tools, artifact references, freshness, groundedness, policy result, caveats, assistant session ID, and correlation ID.

#### Scenario: Audit record is linked to answer

- **WHEN** audit persistence succeeds
- **THEN** `research_metadata` SHALL include `research_answer_audit_id`.

#### Scenario: Audit persistence fails

- **WHEN** the audit record cannot be stored
- **THEN** the research request SHALL fail closed
- **AND** the assistant session SHALL NOT be marked successful.

#### Scenario: File observability is active

- **WHEN** a research audit is persisted
- **THEN** the system SHOULD emit `RESEARCH_ANSWER_AUDITED` without copying raw prompt or full answer content into the event.

---

### Requirement: Tests and documentation shall prove completion

The implementation SHALL include tests and operator documentation.

#### Scenario: Focused tests are inspected

- **THEN** tests SHALL cover all new intent classifications, deterministic plans, central tool policy, tool execution, template injection, source references, metric grounding, policy rewrite, pre-synthesis failure, and answer-audit persistence.

#### Scenario: Documentation is inspected

- **THEN** `vnalpha/docs/assistant-research-intelligence-tools.md` SHALL explain the workflow, tools, templates, groundedness, policy, deterministic fallback, audit metadata, and failure behavior.

#### Scenario: Validation evidence is reviewed

- **THEN** `validation.md` SHALL list focused and repository-wide commands
- **AND** SHALL not claim unexecuted commands passed.
