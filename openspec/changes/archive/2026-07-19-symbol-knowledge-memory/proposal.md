# Proposal: Symbol Knowledge Memory and Compaction

## Summary

Add a durable symbol-memory capability that continuously accumulates verified research knowledge without allowing active Markdown files or assistant context to grow without bound.

The user-facing model is intentionally simple:

```text
one active Markdown knowledge card per symbol
```

For example:

```text
<openstock-state-root>/knowledge/symbols/FPT.md
<openstock-state-root>/knowledge/symbols/HPG.md
<openstock-state-root>/knowledge/symbols/VNM.md
```

Each file is a compact, human-readable materialized view of the symbol knowledge that is currently active. It is not the canonical audit history and it is not an append-only chat transcript.

The canonical history is stored as structured events and claims in DuckDB plus bounded archive artifacts:

```text
validated research evidence
  -> immutable memory event
  -> typed temporal claim
  -> claim lifecycle resolution
  -> compact per-symbol Markdown card
  -> bounded context retrieval
```

## Why

OpenStock currently produces useful symbol evidence through candidate scores, feature snapshots, research tools, notes, assistant answers, and research artifacts. That evidence is mostly consumed per command or per workspace. The system does not yet maintain a durable, corrected, compact body of knowledge for each symbol.

A naive implementation that appends every conversation or result into one `MEMORY.md` file would create several problems:

- active context would grow indefinitely;
- stale and current observations would be mixed together;
- incorrect hypotheses could remain visible after stronger evidence appears;
- repeated summarization would create summary drift;
- historical queries could accidentally consume future information;
- user-authored notes could be overwritten by automated compaction;
- source provenance and correction history would be difficult to audit.

OpenStock needs memory that can learn over time while remaining bounded, temporal, source-grounded, reviewable, and recoverable.

## Goals

- Maintain one active Markdown knowledge card per stock symbol.
- Keep Markdown cards small enough for human review and bounded context retrieval.
- Persist immutable memory events and structured claims separately from Markdown.
- Continuously update symbol knowledge from validated, persisted research evidence.
- Support explicit user-authored notes without treating them as verified market facts.
- Replace inaccurate or stale information in the active view through explicit claim lifecycle transitions.
- Preserve superseded, expired, rejected, and conflicted claims in audit history rather than silently deleting them.
- Require source references and temporal metadata for factual and numeric claims.
- Prevent future information from entering historical as-of analysis.
- Compact memory deterministically from structured claims rather than summarizing summaries.
- Bound prompt memory through retrieval budgets independent of archive size.
- Provide commands to inspect, add, correct, compact, repair, and audit memory.
- Preserve the research-only product boundary.

## Non-goals

- No broker, order, account, portfolio, allocation, margin, transfer, or trading-execution capability.
- No unrestricted filesystem, SQL, shell, network, or generated-code access.
- No automatic external data fetching initiated by memory maintenance.
- No storage of full chat transcripts in symbol knowledge cards.
- No automatic promotion of every assistant answer or tool output into durable knowledge.
- No vector database requirement in the initial implementation.
- No autonomous declaration that a disputed claim is true without a deterministic authority rule, newer validated evidence, or explicit user resolution.
- No hard deletion of audit evidence merely because a claim is no longer active.
- No replacement of canonical warehouse data or research artifacts with Markdown prose.

## User-facing behavior

### Active symbol card

The active document for a symbol SHALL contain only selected, current knowledge, such as:

```text
current snapshot
durable facts
active hypotheses
risks and caveats
recent changes
important rejected hypotheses
open questions
user-authored notes
source references
```

It SHALL NOT contain every observation, every tool result, or the complete conversation history.

### Continuous updates

After a validated research artifact or trusted deterministic tool output is persisted, the memory service MAY normalize eligible evidence into memory events and claims. The service SHALL NOT promote raw model prose directly into factual memory.

Examples of eligible inputs include:

- candidate score snapshots;
- feature snapshots;
- market and sector snapshots;
- deep-symbol analysis artifacts;
- validated research automation artifacts;
- explicit user memory commands;
- user corrections and pin/unpin actions;
- data-quality resolution events.

### Correction and removal of inaccurate information

“Inaccurate information removal” means removal from the active symbol card and default retrieval context, not destruction of audit history.

A claim MAY leave the active view only when one of the following occurs:

- newer authoritative evidence supersedes it;
- its configured validity period expires;
- deterministic validation rejects it;
- a conflict is explicitly resolved;
- the user corrects or rejects it;
- a referenced source is invalidated and no valid support remains.

The system SHALL record why the claim changed state and what evidence caused the transition.

### Bounded context

When answering a symbol question, the assistant SHALL retrieve a bounded context package containing only relevant, temporally valid knowledge. The size of the on-disk archive SHALL NOT determine prompt size.

## Scope

### Memory objects

The implementation SHALL define typed contracts equivalent to:

```text
MemoryEvent
MemoryClaim
MemoryDocument
MemoryCompactionRun
MemoryRetrievalResult
```

### Claim lifecycle

Claims SHALL support at least:

```text
active
superseded
expired
rejected
conflicted
pinned
```

A claim SHALL include at least:

```text
claim_id
entity_type
entity_id
claim_type
predicate
value
status
confidence
observed_at
as_of_date
valid_from
valid_until or expiry policy
source references
supersedes reference when applicable
created_by origin
```

### Markdown document contract

Each symbol card SHALL have versioned frontmatter and separate system-managed and user-managed sections. Automated compaction SHALL preserve user-authored sections exactly unless the user explicitly requests normalization.

### Retrieval

Retrieval SHALL prioritize exact symbol and date filtering before optional semantic ranking. Historical requests SHALL exclude claims that were not available by the requested date.

### Compaction

Compaction SHALL:

- deduplicate equivalent claims;
- retain active and pinned knowledge;
- expire or archive stale observations;
- preserve important rejected hypotheses;
- expose unresolved conflicts;
- preserve user sections;
- produce a dry-run diff;
- be idempotent when no new evidence exists;
- update the Markdown document through an atomic write;
- record before/after counts, token estimates, hashes, and source coverage.

### Commands

The command surface SHOULD include:

```text
/memory status
/memory show SYMBOL
/memory remember SYMBOL "note"
/memory correct SYMBOL <claim-id> "correction"
/memory pin <claim-id>
/memory unpin <claim-id>
/memory conflicts [SYMBOL]
/memory sources SYMBOL
/memory compact SYMBOL --dry-run
/memory compact SYMBOL --execute
/memory repair [SYMBOL]
/memory rebuild-index
```

Command names MAY be adjusted to fit the accepted unified command catalog, but the behavior and safety requirements SHALL remain.

## Success criteria

This change is complete only when:

```text
- one bounded active Markdown card can be maintained per symbol;
- raw chat history is not copied into symbol cards;
- structured event and claim history is persisted independently;
- every factual or numeric active claim has temporal metadata and source references;
- user notes remain distinguishable from verified claims;
- newer validated evidence can supersede inaccurate active claims;
- superseded and rejected claims remain auditable;
- conflicts are visible and are not silently resolved;
- repeated compaction without new evidence is idempotent;
- user-authored Markdown blocks survive compaction unchanged;
- historical retrieval rejects future knowledge;
- active prompt memory remains within a configured token budget;
- corrupt or externally modified documents can be detected and repaired or quarantined;
- concurrent writers do not lose events or corrupt Markdown;
- memory content is treated as untrusted historical reference, not executable instruction;
- the research-only product boundary remains unchanged.
```

## Dependencies

This change depends on:

- `openstock-four-phase-hardening` for repository, migration, locking, lifecycle, redaction, and evaluation discipline;
- `research-intelligence-data-model-foundation` for lineage-aware structured research objects and repository conventions.

Adapters that consume the complete deep-symbol artifact contract may be implemented after or alongside `deep-symbol-analysis-engine`; the core memory store and explicit user-note workflow do not require that engine to be complete.

## Validation direction

Implementation PRs must include focused tests for:

```text
claim lifecycle transitions
source and numeric grounding
historical as-of filtering
compaction idempotency
managed/user Markdown preservation
concurrent update safety
atomic writes and recovery
bounded retrieval
prompt-injection isolation
migration compatibility
command behavior and dry-run semantics
```

Expected repository validation includes:

```bash
make repo-hygiene
make lint-vnalpha
make test-vnalpha
make verify-r4
packaging/scripts/openstock-verify --ci
```

## Product boundary

Symbol memory is a research knowledge system. It may preserve observations, hypotheses, caveats, rejected hypotheses, user notes, and source-grounded summaries.

It SHALL NOT create or execute trades, access broker or account state, manage portfolios or allocation, or convert research claims into personalized execution instructions.