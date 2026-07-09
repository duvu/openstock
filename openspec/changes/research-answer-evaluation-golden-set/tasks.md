# Tasks: Research Answer Evaluation Golden Set

## 0. Governance

- [ ] 0.1 Evaluate research quality without optimizing for trade execution.
- [ ] 0.2 Treat policy safety as a hard gate.
- [ ] 0.3 Do not use golden sets to encode personalized investment advice.

## 1. Golden set layout

- [ ] 1.1 Add research answer golden case schema.
- [ ] 1.2 Add scenario plan golden case schema.
- [ ] 1.3 Add policy refusal golden case schema.
- [ ] 1.4 Add historical evidence golden case schema.
- [ ] 1.5 Add shortlist golden case schema.

## 2. Evaluation checks

- [ ] 2.1 Add groundedness check.
- [ ] 2.2 Add required caveat check.
- [ ] 2.3 Add missing-data disclosure check.
- [ ] 2.4 Add forbidden phrase/policy check.
- [ ] 2.5 Add artifact reference integrity check.

## 3. Runner

- [ ] 3.1 Add eval runner.
- [ ] 3.2 Add CI mode.
- [ ] 3.3 Add human-readable report.
- [ ] 3.4 Add failing examples.

## 4. CI and documentation

- [ ] 4.1 Add `make eval-research-answers`.
- [ ] 4.2 Document how to add new golden cases.
- [ ] 4.3 Add minimal seed cases for each evaluation family.

## 5. Validation

- [ ] 5.1 Run standard tests.
- [ ] 5.2 Run eval command in CI mode.
