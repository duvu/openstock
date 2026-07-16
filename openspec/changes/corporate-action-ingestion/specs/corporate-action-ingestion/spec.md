## ADDED Requirements

### Requirement: Provider-independent corporate-action evidence

OpenStock SHALL expose a canonical `reference.corporate_actions` provider
contract with stable IDs, normalized action types, relevant dates and terms,
source provenance, content hashes and preserved raw payloads.

#### Scenario: Provider returns no actions

- **WHEN** a supported provider returns a valid empty response
- **THEN** the result is distinguishable from unsupported or failed access
- **AND** the exact canonical columns remain present

### Requirement: Raw-first validation

OpenStock SHALL persist source evidence before deciding whether an action may be
promoted to the canonical action registry.

#### Scenario: Malformed action terms

- **WHEN** a cash dividend has no positive cash amount or a ratio action has no
  positive ratio
- **THEN** the evidence remains in raw storage
- **AND** a quarantine record identifies the failed validation rules
- **AND** no canonical action is created

### Requirement: Idempotent revision lineage

OpenStock SHALL make repeated ingestion idempotent and preserve every material
revision instead of overwriting prior evidence.

#### Scenario: Provider revises one event

- **WHEN** the same provider/event ID arrives with changed canonical terms
- **THEN** a new revision supersedes the prior revision
- **AND** an affected-range signal identifies the earliest relevant date

### Requirement: Conflict preservation

OpenStock SHALL preserve conflicting current source evidence without selecting a
winner implicitly.

#### Scenario: Two providers disagree

- **WHEN** two sources report materially different terms for the same
  symbol/action/date
- **THEN** both revisions remain queryable
- **AND** the current canonical status is `CONFLICT`
- **AND** the sync result is partial rather than complete

#### Scenario: One provider revises conflicting terms

- **WHEN** one source revises its event after a cross-provider conflict
- **THEN** only that source's prior revision is superseded
- **AND** matching revised terms converge to one shared active revision
- **AND** non-matching current alternatives remain preserved as `CONFLICT`

### Requirement: Lifecycle-aware symbol resolution

OpenStock SHALL reconcile action symbols against current or historical symbol
identity and SHALL quarantine unresolved identities.

### Requirement: Scope separation

Issue #112 SHALL NOT calculate adjustment factors, adjusted OHLCV or downstream
price-basis propagation. Those remain owned by #113 and #114.
