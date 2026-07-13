# Symbol Knowledge Memory

Symbol memory is a research-only, symbol-scoped knowledge capability. It never
places trades, fetches data autonomously, or treats stored text as executable
instruction. Current policy and validated tool output always take precedence.

## Storage and Markdown contract

The canonical history is DuckDB: `memory_event` is append-only and
`memory_claim` holds typed temporal claims. `memory_document` indexes the active
card and `memory_compaction_run` records each materialization. Markdown is a
reviewable materialized view, not the audit source of truth.

The user-state root contains:

```text
knowledge/
  symbols/<SYMBOL>.md
  archive/events/YYYY/MM/<SYMBOL>-<digest>.jsonl.gz
  quarantine/
  manifests/
  exports/
```

Each card has versioned frontmatter, one managed region, and one user region.
The managed region is generated from eligible structured claims. Automated
compaction preserves the user region byte-for-byte. Do not manually change
frontmatter or managed markers; use `/memory repair SYMBOL` if they are damaged.
External valid edits are detected and audited. Malformed cards are moved to
`knowledge/quarantine/` rather than overwritten.

## Claims and lifecycle

Claims are typed as facts, observations, hypotheses, risks, data-quality
caveats, user notes, or open questions. A user note remains user-authored and
unverified. Validated factual claims require a source reference and temporal
metadata. Admission resolves that reference against the persisted source row;
raw assistant or chat text, relabeled transcripts, and unknown source kinds are
rejected.

Active claims can become `superseded`, `expired`, `rejected`, or `conflicted`.
Newer authoritative evidence may supersede matching older evidence. Equal
authority disagreement remains visible as a conflict. Expiry is claim-type
specific. A correction records a new event and changes memory lifecycle state;
it never rewrites canonical warehouse evidence. Historical claims and events
remain auditable after removal from the active card.

## Compaction, archive, and retrieval budgets

Micro-compaction applies lifecycle expiry and rematerializes only the affected
symbol. Macro compaction renders from structured claims, preserves user content,
uses atomic replacement, and stores before/after metadata. `/memory compact
SYMBOL --dry-run` is read-only; omit `--dry-run` to execute.

`MemoryCompactionPolicy` sets the per-card token budget and uncompacted-event
threshold. `MemoryContextBudget` sets a total prompt budget and optional section
budgets for facts, context, risks, and user notes. Retrieval selects whole
claims, filters future or inactive claims, exposes conflicts/caveats/missing
data, and labels all output as untrusted historical reference. Archive growth
does not expand the retrieval budget.

Archive rotation copies eligible events into compressed JSONL files and records
event IDs in a manifest. It never deletes source evidence or canonical events.

Run `vnalpha eval symbol-memory-runtime --ci` to replay correction, conflict,
compaction, temporal-filtering, and source-grounding scenarios against actual
memory events, claims, retrieval, and cards. The separate `research-runtime`
corpus verifies assistant context isolation.

## Commands and operations

```text
/memory status
/memory show SYMBOL
/memory remember SYMBOL "note"
/memory correct SYMBOL CLAIM_ID "correction"
/memory pin CLAIM_ID
/memory unpin CLAIM_ID
/memory conflicts SYMBOL
/memory sources SYMBOL
/memory compact SYMBOL --dry-run
/memory compact SYMBOL
/memory repair SYMBOL
/memory rebuild-index
/memory maintain [YYYY-MM-DD]
```

`/memory status` intentionally exposes aggregates only: availability, claim
counts, conflicts, freshness, archive size, budgets, and compaction state. It
does not expose note bodies. Lifecycle logs likewise contain IDs, statuses,
hashes, counts, token estimates, source coverage, and duration, never raw notes.

For recovery, run `/memory repair SYMBOL` first. A valid card missing its index
metadata is reindexed without rewriting content. A malformed card is
quarantined; inspect that copy, repair the source material, then rerun
compaction. `/memory rebuild-index` reacquires document indexes from canonical
claims and is serialized by the root maintenance lock. Per-symbol updates use
separate locks, so unrelated symbols can proceed independently.

`/memory maintain` runs bounded expiry, card refresh, and event archival work;
an optional date makes the lifecycle cutoff explicit for an operator run.
