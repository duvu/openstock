# Tasks: Research Answer Evaluation Golden Set

## 0. Governance

- [x] 0.1 Evaluate research quality without optimizing for trade execution.
- [x] 0.2 Treat policy safety as a hard gate.
- [x] 0.3 Do not use golden sets to encode personalized investment advice.

## 1. Golden set layout

- [x] 1.1 Add research answer golden case schema.
- [x] 1.2 Add scenario plan golden case schema.
- [x] 1.3 Add policy refusal golden case schema.
- [x] 1.4 Add historical evidence golden case schema.
- [x] 1.5 Add shortlist golden case schema.

## 2. Evaluation checks

- [x] 2.1 Add groundedness check.
- [x] 2.2 Add required caveat check.
- [x] 2.3 Add missing-data disclosure check.
- [x] 2.4 Add forbidden phrase/policy check.
- [x] 2.5 Add artifact reference integrity check.

## 3. Runner

- [x] 3.1 Add eval runner.
- [x] 3.2 Add CI mode.
- [x] 3.3 Add human-readable report.
- [x] 3.4 Add failing examples.

## 4. CI and documentation

- [x] 4.1 Add `make eval-research-answers`.
- [x] 4.2 Document how to add new golden cases.
- [x] 4.3 Add minimal seed cases for each evaluation family.

## 5. Validation

- [x] 5.1 Run standard tests.
- [x] 5.2 Run eval command in CI mode.
