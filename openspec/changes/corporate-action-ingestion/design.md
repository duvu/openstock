# Design: Corporate-action ingestion

## Boundaries

`vnstock` owns provider access and normalization. `vnalpha` owns persistence,
validation and reconciliation. Neither layer infers an action from a price gap.
KBS and VCI are market-data evidence sources; they are not labelled as official
issuer disclosures.

## Provider contract

The dataset is `reference.corporate_actions`. Every row includes a provider event
ID, symbol, normalized action type, source reference/version, content hash and
raw source payload. Dates and economic terms are optional because providers may
publish partial records; vnalpha decides whether the record can be canonical.
Ratios use one provider-independent convention: new/resulting shares per existing
share, while the original provider wording remains available in `ratio_text`.

KBS and VCI declare the capability as `partial`. Empty responses are valid empty
results. Other providers remain unsupported unless they implement the same
contract explicitly.

## Canonical storage

Raw evidence is inserted before canonical validation. Four additional contracts
separate failure boundaries:

- `corporate_action`: immutable canonical revisions and current status;
- `corporate_action_source_link`: source-to-revision provenance;
- `corporate_action_quarantine`: malformed, unclassified or unresolved identity;
- `corporate_action_affected_range`: deterministic invalidation input for #113.

## Identity and revisions

A provider event ID is stable within a provider. A changed content hash for the
same provider event reuses the canonical action ID and creates a new revision.
Identical evidence from another provider links to the existing revision. A
materially different revision for the same symbol/action/date is retained and
all current alternatives are marked `CONFLICT`; no provider silently wins. A
provider revision supersedes only that provider's prior revision. If the revised
terms match another current source, the conflict converges to the shared active
revision; otherwise the remaining alternatives stay `CONFLICT`.

## Validation

Canonical promotion requires:

- known action taxonomy;
- at least one relevant date;
- positive cash amount for cash dividends;
- positive ratio for stock/bonus/split/consolidation/rights events;
- non-negative subscription terms;
- symbol identity present in current or historical lifecycle storage.

Rejected records remain queryable in quarantine with stable rule IDs.

## Commands

```text
vnalpha sync corporate-actions SYMBOL [--start DATE --end DATE --source PROVIDER]
vnalpha data download corporate-actions SYMBOL [...]
vnalpha data status corporate-actions [SYMBOL]
```

All commands are read-only with respect to brokers, accounts and execution.
