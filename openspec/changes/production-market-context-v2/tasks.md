## 1. Versioned policy contracts

- [x] 1.1 Add immutable validated `v1` and production `v2` policies for market regime and sector strength.
- [x] 1.2 Preserve explicit `v1` behavior while making builders default to production `v2`.
- [x] 1.3 Make benchmark trend and volatility thresholds policy-controlled.

## 2. Production market-regime evidence

- [x] 2.1 Filter exact-date features by completeness profile, common-equity classification, staleness and liquidity.
- [x] 2.2 Enforce minimum eligible count, breadth, exchange and liquidity coverage.
- [x] 2.3 Persist policy thresholds, exclusions, coverage and additional breadth metrics in lineage.
- [x] 2.4 Return explicit insufficient-data quality rather than classifying five arbitrary rows.

## 3. Production sector-strength evidence

- [x] 3.1 Enforce security-type, profile, staleness, metadata, taxonomy and liquidity eligibility.
- [x] 3.2 Exclude or degrade sparse and incomplete sectors according to versioned policy.
- [x] 3.3 Apply deterministic winsorization, robust medians and configurable normalized score weights.
- [x] 3.4 Persist sector coverage, outlier adjustments, concentration and taxonomy evidence.

## 4. Readiness, tests and documentation

- [x] 4.1 Require production methodology and coverage in deep-analysis readiness.
- [x] 4.2 Add golden fixtures for risk-on, risk-off, mixed, insufficient, sparse, outlier and concentration cases.
- [x] 4.3 Preserve legacy builder regression tests through explicit `v1` policies.
- [x] 4.4 Document the production methodology and compatibility boundary.
- [x] 4.5 Run full CI, package build and record exact final-SHA evidence before closing #84. [evidence: `openstock-ci` run #35 passed on implementation SHA `661f35ce1aebe7bc8e56b6f7490686cd2cfaa9a2`]
