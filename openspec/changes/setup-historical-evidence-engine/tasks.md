# Tasks: Setup Historical Evidence Engine

## 0. Governance

- [ ] 0.1 Keep evidence output research-only.
- [ ] 0.2 Do not present historical evidence as prediction certainty.
- [ ] 0.3 Include small-sample caveats.

## 1. Data and cohorts

- [ ] 1.1 Define setup cohort contract.
- [ ] 1.2 Build cohorts from persisted candidate scores and outcomes.
- [ ] 1.3 Add regime and sector split support when available.
- [ ] 1.4 Persist or cache setup evidence snapshots.

## 2. Metrics

- [ ] 2.1 Compute sample size.
- [ ] 2.2 Compute forward return distribution.
- [ ] 2.3 Compute outcome rate.
- [ ] 2.4 Compute FAE/AAE stats.
- [ ] 2.5 Compute regime split.
- [ ] 2.6 Attach caveats.

## 3. Commands and assistant

- [ ] 3.1 Add `/setup-evidence`.
- [ ] 3.2 Add `evidence.get_setup_history` tool.
- [ ] 3.3 Add assistant intent `review_setup_evidence`.
- [ ] 3.4 Add synthesis template.

## 4. Tests

- [ ] 4.1 Test evidence output for known setup type.
- [ ] 4.2 Test small sample caveat.
- [ ] 4.3 Test missing outcome data handling.
- [ ] 4.4 Test no prediction certainty.

## 5. Validation

- [ ] 5.1 Run standard validation commands and attach evidence.
