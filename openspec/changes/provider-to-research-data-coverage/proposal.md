# Change: Provider-to-research data coverage

## Status

Proposed. This change is the normative program specification for #327 and child issues #328–#336, #341 and #342. It begins only after the queue/runtime contracts in #317 are stable enough to provide typed bounded acquisition.

## Why

`vnstock` and `vnalpha` currently expose different meanings of dataset support:

```text
registered contract
≠ REST route
≠ provider capability
≠ quality readiness
≠ vnalpha client/persistence
≠ deterministic research consumer
≠ point-in-time eligibility
```

The core quant loop already has its required external inputs: symbol reference, equity OHLCV and index OHLCV. Remaining gaps affect optional current context and deeper point-in-time research:

- company profile and session data have no bounded `vnalpha` consumer;
- fundamental contracts lack reliable publication/revision semantics;
- official disclosures are absent from the provider-independent layer;
- no dedicated point-in-time share-count path exists;
- current index membership snapshots cannot establish historical membership;
- `foreign_flow.daily` is contract-only;
- official corporate-action evidence is not reconciled into adjusted-price lineage;
- valuation components are not integrated with verified point-in-time facts;
- route/contract/provider documentation can drift.

## What Changes

### Tier 0 — existing core, unchanged

```text
reference.symbols
equity.ohlcv
index.ohlcv
```

These remain the only external datasets required by existing `PRICE_ANALYSIS` and `CANDIDATE_RANKING` capabilities.

### Tier 1 — optional current context

- `reference.company_info` → bounded company context (#329).
- `equity.quote` and `equity.intraday_trades` → one session summary, not a tick platform (#330).
- `foreign_flow.daily` → one verified daily provider-to-context vertical (#336).

Tier-1 absence is disclosed and never blocks existing price/ranking capabilities.

### Tier 2 — point-in-time foundations

- publication-aware fundamental statement contracts (#331);
- immutable fundamental revisions and as-of snapshots (#332);
- official disclosure metadata and verified events (#333);
- effective-dated share-count facts (#334);
- effective-dated index membership revisions (#335).

Historical consumers may use a fact only when its publication/effective/revision semantics establish that it was observable at the requested date.

### Tier 3 — bounded derived consumers

- reconcile supported verified official actions into canonical corporate-action/adjusted-price lineage (#341);
- build optional valuation context from verified price, fundamental, share-count and taxonomy inputs (#342).

### Cross-cutting inventory

A machine-readable capability inventory distinguishes contract, route, provider, quality, client, consumer, point-in-time and queue status for every built-in dataset (#328).

## Impact

### `vnstock`

- Adds or enriches provider-independent contracts and quality rules.
- Adds only verified routes/provider paths with truthful support levels.
- Removes unsupported `fund.holdings` route drift.
- Keeps provider-specific SDKs and field mapping outside `vnalpha`.

### `vnalpha`

- Adds bounded clients, persistence and deterministic consumers only where a named research use exists.
- Uses the finite queue goal/enrichment contracts from #338.
- Preserves current-only observations separately from historical-eligible facts.
- Keeps every new dataset optional for existing core capabilities.

### Compatibility

- Existing core analysis and ranking remain unchanged when optional data is unavailable.
- Existing provider outputs may remain usable as `CURRENT_ONLY` while new historical-safe metadata is introduced.
- No existing historical consumer may silently reinterpret a current snapshot as point-in-time evidence.

## Dependencies

- Queue and typed goal foundations from #317/#338.
- Existing source-policy and licensing/persistence checks.
- Existing point-in-time symbol/taxonomy and corporate-action schemas where applicable.
- Existing adjusted-price foundation for #341.

## Migration Strategy

1. Publish the capability inventory and remove route/contract drift.
2. Add Tier-1 current-context consumers.
3. Add publication/revision metadata to provider contracts.
4. Persist Tier-2 immutable facts and as-of resolvers.
5. Add bounded Tier-3 reconciliation and valuation consumers.
6. Synchronize accepted implemented requirements into main specs only after validation evidence exists.

## Non-Goals

- No universal accounting ontology or full vendor-field mirror.
- No data lake, external metadata service or generic ETL platform.
- No general web/news crawler, PDF/OCR or semantic document search.
- No full tick database or streaming runtime.
- No fund-research product.
- No forecasts, DCF, target prices, portfolio optimization or trading execution.
- No new mandatory gate for existing price/ranking analysis.
