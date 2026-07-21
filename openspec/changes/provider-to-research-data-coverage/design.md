# Design: Provider-to-research data coverage

## Context

OpenStock separates provider access from research consumption:

```text
vnstock = provider plugins, normalization, canonical contracts, quality and read-only delivery
vnalpha = ingestion evidence, point-in-time persistence, deterministic research consumers
```

A dataset is not production-available merely because one layer contains a name or route. The program therefore treats support as a chain of independently verified states.

## Goals

- Make dataset support truthful and machine-readable.
- Close bounded provider-to-consumer gaps with one vertical at a time.
- Establish explicit point-in-time eligibility for historical research.
- Reuse the finite queue goals from #338 without adding private payload types.
- Keep optional data outside existing price/ranking readiness.
- Preserve provider, source, publication, revision and methodology lineage.

## Non-Goals

- A universal financial-data ontology.
- Automatic provider discovery or generic scraping.
- Broad document ingestion, OCR or LLM event verification.
- Fund research, forecasts or trading recommendations.
- A new metadata database or external orchestrator.

## Decision 1: One truthful capability inventory

The checked-in inventory records, per canonical dataset:

```text
contract status
service route
provider support level
quality validator status
vnalpha client status
persistence status
research consumer
point-in-time eligibility
license/persistence policy
queue goal/enrichment mapping
```

Status vocabulary is finite and tested. Contract registration, route presence and provider delivery remain separate facts.

Confirmed drift decisions:

- `foreign_flow.daily` remains contract-only/deferred until #336 completes.
- unsupported `fund.holdings` route is removed; no placeholder fund warehouse is created.

## Decision 2: Consumer before persistence

A new warehouse table or queue acquisition path is added only when a named deterministic consumer exists. Every vertical delivers a bounded chain:

```text
provider-independent contract
→ verified provider or truthful unsupported status
→ route + quality/provenance
→ vnalpha typed client
→ bounded persistence
→ deterministic consumer
```

## Decision 3: Explicit point-in-time states

Every persisted observation declares whether it is:

```text
CURRENT_ONLY
HISTORICAL_ELIGIBLE
AMBIGUOUS_OR_QUARANTINED
```

Historical eligibility requires observable publication/available-from or effective-date evidence. Fiscal period end, current observation time or current membership MUST NOT be substituted for historical availability.

Immutable revisions and supersession links preserve changes rather than overwriting prior evidence.

## Decision 4: Queue integration is finite and optional

Optional current-symbol enrichments use `ENSURE_CURRENT_SYMBOL` with normalized enrichments:

```text
COMPANY_CONTEXT
SESSION_CONTEXT
FUNDAMENTAL_CONTEXT
OFFICIAL_EVENT_CONTEXT
SHARE_COUNT_CONTEXT
FLOW_CONTEXT
VALUATION_CONTEXT
```

Bounded history or entity/date acquisition uses `SYNC_DATASET_RANGE`.

Historical replay reads persisted evidence and never auto-enqueues current data. Missing optional data never invalidates existing core artifacts.

## Decision 5: Company context remains current-state evidence

`reference.company_info` is persisted as a versioned current snapshot with provider, observed time and content hash.

- Current share fields are informational only.
- Current industry fields do not replace dated classification history.
- Historical consumers reject current-only fields unless explicitly requesting latest context.

## Decision 6: Session context is a bounded summary

Quote and intraday trades produce one per-symbol/session summary:

```text
last/close and observed time
accumulated volume
intraday high/low
trade count and matched volume
simple VWAP
optional buy/sell/unknown split
freshness and coverage caveats
```

`vnalpha` does not persist an unbounded tick history. Valid market-closed empty, unsupported, stale and provider failure remain distinct.

## Decision 7: Fundamentals use a common publication-aware envelope

The four existing statement contracts share a bounded metadata envelope:

```text
fiscal period and period end
statement scope
audit status
currency and unit
published_at and available_from
source reference/version/content hash
revision identity and supersession
historical_as_of_eligible
```

Only a small common fact set is normalized initially:

```text
revenue
net_income
eps
total_assets
total_equity
total_liabilities
operating_cash_flow
```

`fundamental_snapshot(symbol, as_of_date)` selects only observable eligible revisions and exposes missing scope/unit/period evidence.

## Decision 8: Official disclosures provide verified metadata, not document intelligence

`reference.official_disclosures` stores bounded metadata and a small allowlisted event set. Only configured official-source adapters may emit `VERIFIED` records.

`FINANCIAL_REPORT_PUBLISHED` may include typed fiscal-period, scope and issuer-document identity when supplied by the official source. #332 links verified publication occurrences to matching statement revisions; ambiguous/title-only matches remain unlinked and historical-ineligible.

No PDF/OCR, generic crawler or LLM verification is introduced.

## Decision 9: Share counts are dedicated effective-dated facts

`reference.share_count_fact` records shares outstanding, effective/available/publication dates, source authority and immutable revisions.

Current company-info values may be persisted as `CURRENT_ONLY`. Historical queries never substitute the latest value for a missing historical fact.

## Decision 10: Historical index membership uses revisions

`reference.index_membership_revision` stores add/remove/snapshot-member actions with announcement, availability and effective intervals.

Initial end-to-end scope is one configured index family, starting with VN30. Current provider membership snapshots remain historical-ineligible unless linked to effective-dated evidence.

Sector history continues to use existing symbol classification history rather than current sector snapshots.

## Decision 11: Foreign flow is one small daily vertical

The canonical dataset name is chosen once and used consistently across contract, route, provider and client.

Initial fields cover buy/sell/net volume and optional values with arithmetic and duplicate-session checks. The consumer exposes latest and bounded 5/20-session flow context, optionally relative to canonical trading denominators.

No intraday streaming or investor-category ontology is introduced.

## Decision 12: Official actions reconcile into existing canonical action lineage

Supported official events map only to the corporate-action types already handled by the deterministic adjustment subsystem.

- Exact agreement adds official source authority without duplicate action revisions.
- Conflict creates a candidate revision or quarantine evidence; never silent overwrite.
- Accepted revisions emit one affected range and rebuild only the affected adjustment/series interval.
- Raw canonical OHLCV remains unchanged.

## Decision 13: Valuation is an optional bounded consumer

Initial metrics:

```text
P/E and earnings yield
P/B and book yield
historical percentile
sector-relative percentile
```

Every metric references exact price basis/date, fundamental revision, share-count revision, taxonomy evidence and methodology version. Missing, zero, negative or incompatible inputs make only the affected metric unavailable.

No forecasts, DCF, target price or automatic ranking-policy change.

## Migration and Compatibility

- Existing latest/current provider outputs remain readable but may be marked current-only.
- Historical eligibility is introduced additively and fails closed.
- Existing core readiness is unchanged.
- New queue enrichments are versioned through #338.
- Main specs are synchronized only after implementation and validation evidence exists.

## Validation Strategy

- Contract and fixture tests in `vnstock`.
- Immutable revision, as-of boundary and no-lookahead tests in `vnalpha`.
- Queue submit/join/reuse tests for every queued vertical.
- Cross-surface typed-result parity.
- Capability inventory consistency checks across contract, route, provider, client and documentation.
