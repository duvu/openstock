## Why

Issue #84 is the current methodology gate in the OpenStock roadmap. The existing
market-regime and sector-strength builders are deterministic, but their legacy
`v1` thresholds accept very small or weakly classified universes. A technically
valid snapshot can therefore overstate research readiness when breadth,
liquidity, exchange coverage, security type or taxonomy evidence is incomplete.

## What Changes

- Preserve `market-regime-v1` and `sector-strength-v1` as explicit compatibility
  policies.
- Introduce `market-regime-v2` and `sector-strength-v2` as the production
  defaults for builders and deep-analysis readiness.
- Require exact-date, complete feature profiles, common-equity classification,
  minimum liquidity evidence and explicit coverage thresholds.
- Add deterministic breadth evidence for advances/declines, new-high proximity,
  median return and cross-sectional dispersion.
- Apply robust sector aggregation with deterministic winsorization,
  configurable score weights and concentration evidence.
- Persist methodology version, thresholds, coverage, exclusions, taxonomy and
  aggregation evidence in existing snapshot lineage fields.
- Fail closed in readiness when a snapshot is legacy, sparse, illiquid,
  incomplete or below production coverage.

## Capabilities

### Modified Capabilities

- `market-regime-and-sector-context`: production methodology policies,
  eligibility, coverage, robust aggregation and readiness enforcement.

## Impact

- Affects `vnalpha.research_intelligence` market and sector builders.
- Affects deep-analysis context readiness and related deterministic tools.
- Reuses the existing snapshot schema; no destructive warehouse migration is
  required.
- Does not add provider-specific access, LLM ranking, investment advice or any
  broker/account/order behavior.
