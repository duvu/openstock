# Market context methodology

## Status

```text
Current implementation: market-regime-v2 and sector-strength-v2
Compatibility implementation: explicit v1 policy objects
Roadmap owner: GitHub issue #84
Historical conditioning/effectiveness owner: GitHub issue #85
```

Market regime and sector strength are deterministic context artifacts. They do
not produce investment instructions and they do not prove historical alpha.

## Version contract

`v1` preserves the earlier MVP behavior for reproducibility tests and migration
comparison. Production builders and deep-analysis readiness use `v2` by
default. A `v1` snapshot is readable but cannot satisfy production readiness.

## Market-regime v2 eligibility

An observation is eligible only when it is:

- an active `COMMON_EQUITY`;
- classified with an exchange;
- exact-date and not stale;
- complete for `STANDARD_120` or `FULL_252`;
- supported by the minimum average traded-value evidence.

The production policy requires at least 20 eligible symbols, 70% breadth
coverage, 67% exchange coverage and 70% liquidity coverage. When these gates
fail, the builder persists `INSUFFICIENT_DATA` rather than forcing a regime.

Persisted lineage includes active/eligible/excluded counts, coverage ratios,
security/profile/liquidity exclusions, advances/declines, median return,
cross-sectional dispersion and the exact policy thresholds.

## Sector-strength v2 eligibility

A sector is rankable only when it has:

- at least five active members;
- at least four eligible members;
- at least 60% eligible-member coverage;
- production-grade common-equity, completeness and liquidity evidence.

The overall snapshot set additionally requires at least 80% sector metadata,
70% taxonomy coverage and 70% liquidity coverage. Sparse or incomplete sectors
are excluded or explicitly degraded with caveats.

## Classification-metadata readiness contract

Readiness for classification metadata is derived **directly** from the versioned
policy thresholds; no additional unconditional check may override them:

- Sector metadata coverage (`active_metadata_coverage`, equal to
  `1 − unclassified_count / active_count`) must be at least
  `minimum_metadata_coverage` (80% in `sector-strength-v2`). **Bounded missing
  classification is permitted:** a non-zero `unclassified_count` does not fail
  readiness on its own, because it is already encoded in the coverage ratio.
  Residual unclassified symbols above the threshold are disclosed as caveats.
- Taxonomy name/version coverage (over the classified members) must be at least
  `minimum_taxonomy_coverage` (70%).

These two conditions have different remediation paths and are surfaced as
distinct typed diagnostics:

| Condition | Typed issue |
|---|---|
| Metadata coverage below `minimum_metadata_coverage` | `SECTOR_METADATA_INSUFFICIENT` |
| Taxonomy coverage below `minimum_taxonomy_coverage` | `SECTOR_TAXONOMY_INSUFFICIENT` |

Below-threshold coverage is therefore distinguished from ambiguous or invalid
classification (which surfaces through build quality and per-snapshot input
coverage). When both metadata and taxonomy coverage are below threshold, the
missing-classification diagnostic takes precedence because taxonomy coverage is
only meaningful over already-classified members. Snapshot lineage records the
effective policy values (`policy_minimum_metadata_coverage`,
`policy_minimum_taxonomy_coverage`) used by readiness.

## Robust aggregation

Production sector return and relative-strength values are winsorized at the
10th and 90th percentiles before median aggregation. Ranking weights are:

| Evidence | Weight |
|---|---:|
| Relative strength, 20 sessions | 35% |
| Return, 20 sessions | 25% |
| Members above MA20 | 15% |
| Members above MA50 | 10% |
| Leadership share | 15% |

A traded-value concentration ratio above 45% is disclosed as a concentration
warning. Outlier adjustment counts, concentration and taxonomy versions are
stored in lineage.

## Point-in-time membership and classification

Every dated/as-of historical path resolves symbol identity and classification
through the shared resolver in `vnalpha/warehouse/point_in_time.py`
(`resolve_universe`, `resolve_symbol_classification`) over
`symbol_classification_history`, rather than reading current state from
`symbol_master`. This avoids survivorship and taxonomy look-ahead bias when an
old date is recomputed:

- a symbol listed after the requested date is excluded from the universe;
- a symbol delisted on or before the requested date is excluded;
- exchange, security type, sector, industry, taxonomy name and version use the
  interval effective on the requested date;
- overlapping/ambiguous history rows resolve deterministically (latest
  `effective_from`, then highest `source_snapshot_id`) and the symbol is flagged
  ambiguous so production callers can treat it as degraded evidence.

Production breadth and sector builders use this resolver. Snapshot lineage
records `membership_basis` (`symbol_classification_history` or the compatibility
`symbol_master` path), `membership_resolver_version` and, for the resolver, the
coverage/known-symbol counts. `symbol_master` remains the current-state
convenience view; current/latest commands may read it explicitly. Warehouses
without any classification history fall back to the current `symbol_master`
projection so existing/current-only data remains usable.

## Determinism and boundaries

The same warehouse inputs, policy and generation timestamp produce the same
snapshots and ordering. No LLM participates in classification or ranking.
News, documents, fundamentals, broker state, account state and order execution
are outside this methodology.
