# Capability: symbol knowledge projection

## ADDED Requirements

### Requirement: Post-analysis evidence projection after a successful turn

After a successful deep-analysis chat turn whose answer passes both
groundedness and research-policy validation, the application SHALL project the
turn's approved deterministic evidence into the per-symbol knowledge base
through one post-analysis projector that reuses the existing symbol-memory
ingestion, lifecycle and compaction services. No second knowledge store SHALL
be introduced.

#### Scenario: Successful analysis creates deterministic claims and a card
- **GIVEN** persisted candidate score and feature snapshot for FPT
- **WHEN** a `Phân tích FPT` turn succeeds and passes validation
- **THEN** deterministic FPT claims are created or updated and the bounded
  FPT knowledge card is written.

#### Scenario: Only allowlisted persisted evidence is projected
- **WHEN** the projector runs
- **THEN** it projects only evidence backed by a persisted validated artifact
  (candidate score, feature-quality snapshot, market-regime snapshot when
  present), each with exact as-of date and version/provenance fields.

### Requirement: Idempotency and supersession

Repeating the same analysis on unchanged source versions SHALL NOT duplicate
claims. When a later evidence version arrives, the projector SHALL supersede
the prior active claim without deleting historical lineage.

#### Scenario: Repeat projection is idempotent
- **GIVEN** an analysis already projected into memory
- **WHEN** the same analysis on unchanged sources is projected again
- **THEN** no duplicate event or claim is created.

#### Scenario: Newer evidence supersedes prior claim
- **GIVEN** an active claim for a prior as-of date
- **WHEN** newer persisted evidence for the same predicate is projected
- **THEN** the prior claim is superseded and its lineage is preserved.

### Requirement: Raw chat and model prose are never promoted

The projector SHALL reject raw user text, assistant prose and unsupported model
claims as factual memory evidence. It SHALL rely on the existing source-grounding
gate so that no claim can be persisted unless it matches a persisted validated
warehouse artifact.

#### Scenario: Unsupported prose is rejected
- **WHEN** evidence not backed by a persisted artifact is presented
- **THEN** ingestion rejects it and no claim is created.

### Requirement: Failed or partial analysis projects nothing; answers never regress

A failed, partial or policy-rejected analysis SHALL NOT project any claim. A
projection error SHALL be logged and surfaced as a caveat but SHALL NOT fail an
answer that already passed validation.

#### Scenario: Rejected analysis does not project
- **GIVEN** a turn that fails groundedness or policy
- **WHEN** the turn finishes
- **THEN** no projection runs and no claim is created.

#### Scenario: Projection failure does not fail the answer
- **GIVEN** a valid answer whose projection raises
- **WHEN** the projector runs
- **THEN** the answer is still returned and the failure is recorded as a caveat.

### Requirement: Retrieval separation preserved

A later question about the same symbol SHALL retrieve the updated knowledge
context, while current validated warehouse evidence SHALL remain authoritative
over retrieved memory.

#### Scenario: Next turn retrieves updated knowledge
- **GIVEN** a projected FPT claim
- **WHEN** a later FPT question is prepared
- **THEN** the retrieved knowledge context includes the projected claim while
  current warehouse evidence outranks it.
