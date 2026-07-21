## ADDED Requirements

### Requirement: Fundamental contracts SHALL expose publication and revision semantics
The four statement datasets SHALL share a common metadata envelope containing fiscal period, period end, statement scope, audit status, currency, unit, publication/availability time, source identity, content hash, revision identity, supersession and historical eligibility.

#### Scenario: Publication timing is unavailable
- **WHEN** a provider supplies statement values without defensible publication or availability evidence
- **THEN** the values may be used as explicitly current-only context
- **AND** are not eligible for historical as-of snapshots.

#### Scenario: A restatement is received
- **WHEN** content for the same fiscal period changes
- **THEN** a new immutable revision is created
- **AND** the prior revision is linked as superseded rather than overwritten.

### Requirement: Fundamental normalization SHALL remain bounded

#### Scenario: A provider returns a broad vendor statement
- **WHEN** the canonical contract is built
- **THEN** only the approved common fact set is required for this program
- **AND** unsupported vendor fields are not mirrored into a universal accounting model.

### Requirement: Historical fundamental snapshots SHALL use observable revisions only

#### Scenario: A report was published after the requested as-of date
- **WHEN** `fundamental_snapshot(symbol, as_of_date)` is resolved
- **THEN** that statement revision is excluded.

#### Scenario: Consolidated and separate statements both exist
- **WHEN** a snapshot selects facts
- **THEN** it applies the explicit scope preference policy
- **AND** does not mix scopes implicitly.

### Requirement: Verified publication events MAY establish statement availability

#### Scenario: An official publication event identifies one statement revision
- **WHEN** symbol, fiscal period, scope and source/document identity match exactly
- **THEN** the linkage may establish publication/available-from evidence for that revision
- **AND** does not change financial values.

#### Scenario: Publication matching is ambiguous
- **WHEN** multiple statement revisions could match or only title text is available
- **THEN** no revision becomes historical-eligible from that event.

### Requirement: Official disclosures SHALL be bounded verified metadata
The provider layer SHALL expose canonical disclosure metadata and a small allowlisted event set through configured official-source adapters.

#### Scenario: A non-approved source returns a disclosure
- **WHEN** the occurrence is ingested
- **THEN** it cannot emit a `VERIFIED` event.

#### Scenario: A disclosure is revised
- **WHEN** an official correction or replacement is published
- **THEN** a new revision and supersession link are persisted
- **AND** historical queries observe each revision only after its publication time.

### Requirement: Disclosure ingestion SHALL NOT require document intelligence

#### Scenario: A disclosure lacks structured event metadata
- **WHEN** deterministic allowlisted normalization cannot classify it
- **THEN** it remains metadata-only or quarantined
- **AND** no PDF/OCR or LLM inference is used to promote it.

### Requirement: Share counts SHALL be dedicated effective-dated facts

#### Scenario: Current company information includes shares outstanding
- **WHEN** no verified effective and availability dates exist
- **THEN** the observation is stored as current-only
- **AND** is not substituted for a missing historical share count.

#### Scenario: A verified share-count revision exists
- **WHEN** `share_count_as_of(symbol, date)` is resolved
- **THEN** it selects only revisions observable by the date
- **AND** reports missing or ambiguous evidence explicitly.

### Requirement: Index membership SHALL use effective-dated revisions

#### Scenario: VN30 membership changes at a rebalance date
- **WHEN** membership is queried before and after the effective date
- **THEN** `index_members_as_of()` returns the corresponding member set
- **AND** excludes announcements not yet observable at each query date.

#### Scenario: Only a current membership snapshot exists
- **WHEN** historical membership is requested
- **THEN** the current snapshot is rejected as historical evidence unless linked to verified effective-dated revisions.

### Requirement: Point-in-time datasets SHALL remain optional for existing core capabilities

#### Scenario: Fundamental, disclosure, share-count or membership evidence is missing
- **WHEN** price or ranking analysis has its existing required evidence
- **THEN** core readiness is unchanged
- **AND** the missing optional context is disclosed.

### Requirement: Historical workflows SHALL read persisted point-in-time evidence only

#### Scenario: A historical consumer encounters a missing point-in-time fact
- **WHEN** replay or historical research runs
- **THEN** it returns missing or unavailable evidence
- **AND** does not auto-fetch current provider output.
