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

## Determinism and boundaries

The same warehouse inputs, policy and generation timestamp produce the same
snapshots and ordering. No LLM participates in classification or ranking.
News, documents, fundamentals, broker state, account state and order execution
are outside this methodology.
