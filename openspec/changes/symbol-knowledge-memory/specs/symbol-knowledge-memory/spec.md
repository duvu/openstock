# symbol-knowledge-memory Specification Delta

## ADDED Requirements

### Requirement: System shall maintain one active Markdown knowledge card per symbol

The system SHALL maintain at most one active Markdown knowledge card for each normalized stock symbol under the canonical OpenStock knowledge root.

The active card SHALL be a bounded materialized view of current symbol knowledge and SHALL NOT be the canonical store for the complete historical event stream.

#### Scenario: First knowledge is recorded for a symbol

- **WHEN** eligible memory evidence is accepted for symbol `FPT`
- **THEN** the system creates or updates the canonical `FPT.md` symbol card
- **AND** the document uses versioned frontmatter
- **AND** the document contains system-managed sections
- **AND** the document contains a preserved user-authored section
- **AND** no second active Markdown card is created for the same normalized symbol

#### Scenario: Symbol input attempts path traversal

- **WHEN** a memory command or persisted reference supplies a symbol containing path traversal, path separators, an absolute path, a Windows drive path, or a reserved component
- **THEN** the system rejects the symbol before filesystem access
- **AND** does not create or modify a knowledge document outside the canonical knowledge root

### Requirement: Structured events and claims shall be the canonical memory history

The system SHALL persist immutable memory events and typed temporal claims independently from the active Markdown document.

#### Scenario: Validated evidence enters memory

- **WHEN** a persisted, validated research artifact or deterministic tool result is eligible for memory
- **THEN** the system records an immutable memory event
- **AND** records or updates a typed claim with a stable claim ID
- **AND** records entity, predicate, value, status, temporal metadata, source references, origin, and correlation ID
- **AND** the Markdown card is derived from the structured claim state

#### Scenario: Raw assistant prose has no validated evidence

- **WHEN** an assistant answer contains a statement that is not backed by an eligible persisted source reference
- **THEN** the system does not promote that statement into a verified factual claim
- **AND** does not add it to the managed factual sections of the symbol card

### Requirement: Memory ingestion shall continuously process eligible persisted research evidence

The memory service SHALL support event-driven updates after eligible evidence is successfully persisted. It SHALL NOT ingest every conversation turn by default.

#### Scenario: New candidate score is persisted

- **WHEN** a newer eligible candidate score snapshot is persisted for a symbol
- **THEN** the memory service normalizes the symbol and dates
- **AND** records an evidence event
- **AND** reconciles the new observation against existing claims
- **AND** schedules or performs a bounded update of that symbol card only

#### Scenario: Unrelated symbol evidence is persisted

- **WHEN** evidence for `HPG` is persisted
- **THEN** the system does not rewrite `FPT.md` unless an explicit cross-entity dependency requires it

### Requirement: User-authored memory shall remain distinct from verified knowledge

The system SHALL allow explicit user notes while preserving their origin and verification state.

#### Scenario: User records a symbol note

- **WHEN** the user executes `/memory remember FPT "watch whether relative strength broadens"`
- **THEN** the system records an immutable user-note event
- **AND** creates a claim with user-authored origin
- **AND** does not label the note as a verified market fact
- **AND** preserves the note in the user-authored Markdown region

#### Scenario: Automated compaction runs

- **WHEN** a symbol card containing user-authored content is compacted automatically
- **THEN** the user-authored region is preserved byte-for-byte
- **AND** the system does not rewrite the user's wording without explicit user instruction

### Requirement: Active knowledge shall remove inaccurate or stale claims through auditable lifecycle transitions

The system SHALL remove inaccurate, stale, or unsupported claims from the active symbol card and default retrieval context through explicit lifecycle transitions. The system SHALL retain the original event and claim history for audit.

#### Scenario: Newer authoritative evidence supersedes an older claim

- **WHEN** a newer validated source provides a replacement value for the same symbol and predicate
- **AND** the source-authority and temporal rules permit supersession
- **THEN** the older claim is marked `superseded`
- **AND** the new claim becomes active
- **AND** the active Markdown card no longer presents the older claim as current
- **AND** the transition records the previous claim ID and supporting source references

#### Scenario: A short-lived observation expires

- **WHEN** an active technical observation exceeds its configured expiry policy without renewal
- **THEN** the claim is marked `expired`
- **AND** is excluded from the active card and default retrieval
- **AND** remains available for historical audit

#### Scenario: A claim loses all valid support

- **WHEN** all supporting sources for an active claim are invalidated
- **THEN** the claim is rejected or conflicted according to policy
- **AND** the claim is removed from the default active view
- **AND** the source invalidation reason is persisted

#### Scenario: User rejects an inaccurate claim

- **WHEN** the user explicitly corrects or rejects a claim
- **THEN** the system records a user-correction event
- **AND** transitions the claim with a reason
- **AND** does not delete the original evidence
- **AND** does not rewrite canonical warehouse data

### Requirement: Claim authority, numeric grounding, and conflicts shall be deterministic

The system SHALL define source-authority and lifecycle rules by claim type. It SHALL NOT silently choose between unresolved claims of equivalent authority.

#### Scenario: Numeric claim lacks source support

- **WHEN** a candidate active numeric claim has no valid source reference, as-of date, unit or semantic meaning, or required lineage
- **THEN** the claim is rejected from the active card
- **AND** the rejection reason is persisted

#### Scenario: Same-authority sources conflict

- **WHEN** two eligible sources of equivalent authority provide incompatible values for the same symbol, predicate, and effective period
- **THEN** the system marks the claims `conflicted`
- **AND** preserves both claims and their sources
- **AND** renders a bounded conflict notice
- **AND** does not silently select one value

#### Scenario: Conflict is resolved

- **WHEN** a deterministic authority rule, newer validated evidence, or explicit user resolution resolves a conflict
- **THEN** the system records the resolution event
- **AND** activates the resolved claim
- **AND** transitions the competing claim or claims out of the active state

### Requirement: Claim expiry shall be type-specific

The system SHALL support claim-type-specific validity and expiry policies rather than one global time-to-live.

#### Scenario: Candidate score is refreshed

- **WHEN** a newer candidate score is accepted for the same symbol
- **THEN** the prior candidate score claim is superseded according to score policy

#### Scenario: User thesis becomes old

- **WHEN** a user-authored thesis exceeds a freshness threshold
- **THEN** the system may mark it stale
- **AND** does not automatically delete it
- **AND** does not silently convert it into a rejected factual claim

#### Scenario: Rejected hypothesis is useful for recurrence prevention

- **WHEN** a hypothesis is rejected with valid evidence
- **THEN** the system may retain it in a bounded rejected-hypothesis section or archive
- **AND** may retrieve it when it prevents repeating the same unsupported conclusion

### Requirement: Compaction shall keep active memory bounded without summary drift

The system SHALL compact symbol memory from canonical structured claims and events. It SHALL NOT rely on repeatedly summarizing the previous Markdown summary as the sole evidence source.

#### Scenario: Symbol card exceeds its budget

- **WHEN** the managed content exceeds the configured token budget or compaction threshold
- **THEN** the system classifies active, pinned, expired, superseded, rejected, and conflicted claims
- **AND** deduplicates equivalent claims
- **AND** retains active and pinned knowledge
- **AND** preserves relevant risks, conflicts, open questions, and important rejected hypotheses
- **AND** archives eligible stale claims and events
- **AND** re-renders the managed Markdown sections from structured claims

#### Scenario: Compaction is previewed

- **WHEN** the user executes `/memory compact FPT --dry-run`
- **THEN** the system reports retained, archived, pinned, and conflicted claim counts
- **AND** reports source coverage and before/after token estimates
- **AND** presents the proposed change or diff summary
- **AND** does not mutate claims, documents, indexes, or archives

#### Scenario: Compaction is repeated without new input

- **WHEN** compaction runs again with unchanged claims, policies, and user content
- **THEN** the managed content hash remains unchanged
- **AND** no duplicate archive entries are created
- **AND** the operation is idempotent

### Requirement: Markdown writes shall be atomic and recoverable

The system SHALL protect active symbol cards against concurrent writes, partial files, path replacement, and malformed external edits.

#### Scenario: Two processes update different symbols

- **WHEN** separate processes update `FPT` and `HPG`
- **THEN** symbol-scoped locks allow independent updates without global serialization
- **AND** neither update corrupts the other document

#### Scenario: Two processes update the same symbol

- **WHEN** two processes attempt to update `FPT`
- **THEN** the system serializes the critical section
- **AND** no memory event is lost
- **AND** the final document corresponds to a committed claim generation

#### Scenario: Write fails before atomic replace

- **WHEN** rendering, flushing, validation, or temporary-file writing fails
- **THEN** the previous active Markdown card remains intact
- **AND** the failed update is recorded
- **AND** no partial card becomes active

#### Scenario: Document markers or frontmatter are corrupt

- **WHEN** an active document cannot be validated or safely reconciled
- **THEN** the system quarantines the document or reports repair-required state
- **AND** does not silently overwrite user content
- **AND** unrelated research workflows remain usable

### Requirement: Historical retrieval shall prevent lookahead bias

The system SHALL retrieve claims according to the requested as-of date and SHALL exclude future knowledge from historical analysis.

#### Scenario: Historical analysis is requested

- **WHEN** the user asks for symbol analysis as of `2025-06-30`
- **THEN** the context builder selects only claims whose effective and publication dates were available by `2025-06-30`
- **AND** excludes later candidate scores, reports, corrections, and market context
- **AND** records the as-of date in retrieval metadata

#### Scenario: Current Markdown card contains newer information

- **WHEN** the active Markdown card contains a snapshot newer than the requested historical date
- **THEN** the system retrieves historical claims from the structured store
- **AND** does not use the newer snapshot as historical evidence

### Requirement: Prompt memory shall be bounded independently from archive size

The system SHALL enforce a configured total memory context budget and SHALL retrieve complete claims by priority.

#### Scenario: Archive contains many historical events

- **WHEN** a symbol has thousands of archived memory events
- **THEN** default prompt construction remains within the configured token budget
- **AND** archive size does not automatically increase prompt size

#### Scenario: Selected claims exceed the budget

- **WHEN** all eligible claims cannot fit in the budget
- **THEN** the system selects complete claims according to entity, temporal, pin, authority, relevance, freshness, and duplicate policies
- **AND** does not truncate a claim in the middle
- **AND** records which lower-priority claims were omitted and why

### Requirement: Memory context shall remain subordinate to policy and current evidence

The system SHALL mark memory as untrusted historical reference and SHALL keep current policy and validated tool output authoritative.

#### Scenario: User note contains instructions to bypass policy

- **WHEN** a symbol card or user note contains instructions to choose a tool, ignore policy, fetch data, execute code, or perform trading behavior
- **THEN** the assistant treats the content as reference text only
- **AND** the content cannot alter intent classification, tool selection, approval requirements, or policy enforcement

#### Scenario: Current validated tool output contradicts stale memory

- **WHEN** current validated evidence contradicts a stale memory claim
- **THEN** the current evidence takes precedence in the answer
- **AND** the memory claim is queued for lifecycle reconciliation
- **AND** the assistant discloses unresolved inconsistency when it cannot be deterministically resolved

### Requirement: Memory commands shall expose status, evidence, correction, compaction, and repair

The accepted command surface SHALL expose equivalent behavior for status, symbol inspection, user notes, correction, conflicts, source inspection, compaction, and repair.

#### Scenario: Memory status is requested

- **WHEN** the user executes `/memory status`
- **THEN** the system renders symbol-card count, active claim count, conflict count, stale or expired count, archive size, token budgets, last compaction, and migration availability
- **AND** does not expose raw sensitive note bodies

#### Scenario: Symbol sources are requested

- **WHEN** the user executes `/memory sources FPT`
- **THEN** the system renders active claim IDs, source references, dates, confidence, and lineage summaries

#### Scenario: Memory schema is unavailable

- **WHEN** the warehouse has not completed required memory migrations or the memory service cannot initialize
- **THEN** memory commands return a structured unavailable response with repair or migration guidance
- **AND** the TUI does not crash
- **AND** unrelated research commands may continue

### Requirement: Memory observability shall be bounded and redacted

The system SHALL emit memory lifecycle evidence with stable IDs, statuses, counts, hashes, token estimates, durations, and correlation IDs. It SHALL NOT log raw sensitive note content by default.

#### Scenario: Compaction completes

- **WHEN** a symbol compaction reaches a terminal state
- **THEN** the system persists a compaction run with before/after generation, claim counts, token estimates, source coverage, and output hash
- **AND** emits a bounded lifecycle event linked by correlation ID

### Requirement: Symbol memory shall preserve the research-only boundary

Symbol memory SHALL support research observations, hypotheses, caveats, user notes, source-grounded summaries, and historical audit only.

#### Scenario: Memory content requests trading execution

- **WHEN** a memory note, claim, or correction contains broker, order, account, portfolio, allocation, margin, transfer, or trading-execution instructions
- **THEN** the system does not create an execution capability
- **AND** does not bypass the existing policy boundary
- **AND** treats the content only as untrusted text or rejects it according to existing safety policy