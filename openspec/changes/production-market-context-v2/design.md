# Design: Production market context v2

## Decisions

### Keep legacy policies callable

The existing algorithms remain available as explicit `v1` policy objects.
Production builders default to `v2`; tests that assert the historical behavior
must request `v1` deliberately. This prevents an implicit compatibility mode
from weakening current readiness.

### Use immutable typed policies

`MarketRegimePolicy`, `SectorStrengthPolicy` and `SectorScoreWeights` are frozen
value objects. They validate thresholds at construction and are passed through
load, aggregate, classify, persist and readiness paths. Re-running the same
warehouse inputs, policy and generation timestamp is deterministic.

### Reuse the existing schema

`market_regime_snapshot` and `sector_strength_snapshot` already persist
`methodology_version`, quality, caveats and lineage JSON. Versioned threshold,
coverage and exclusion evidence is written to lineage rather than creating a
second snapshot schema.

### Fail closed on eligibility and coverage

Production market-regime evidence requires:

- at least 20 eligible common equities;
- at least 70% breadth coverage;
- at least 67% exchange coverage;
- at least 70% liquidity coverage;
- exact-date `STANDARD_120` or `FULL_252` complete features;
- average traded value evidence of at least 1,000,000 in the stored units.

Production sector evidence requires:

- at least five active members and four eligible members per ranked sector;
- at least 60% eligible-member coverage;
- at least 80% sector metadata coverage;
- at least 70% taxonomy and liquidity coverage;
- common-equity, exact-date and complete feature eligibility.

Thresholds remain code-versioned constants for this ticket. A later ticket may
load reviewed policy configuration, but no runtime free-form policy input is
introduced here.

### Robust sector aggregation

Sector return and relative-strength inputs are winsorized at the 10th and 90th
percentiles before median aggregation. Ranking uses normalized weights:

- relative strength 20 sessions: 35%;
- return 20 sessions: 25%;
- percent above MA20: 15%;
- percent above MA50: 10%;
- leadership share: 15%.

Concentration above 45% of sector traded-value evidence produces an explicit
caveat. Winsorization counts and concentration ratios are persisted in lineage.

### Readiness requires production methodology

Deep-analysis readiness rejects `v1` snapshots and any `v2` snapshot below the
production thresholds. This avoids treating a legacy or technically generated
snapshot as decision-grade research context.

## Non-goals

- No LLM-generated regime or sector ranking.
- No fundamentals, news or document dependency.
- No order, allocation, account or trading-execution behavior.
- No attempt to prove economic alpha; #85 owns conditioned historical evidence.
