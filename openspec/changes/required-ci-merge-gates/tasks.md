## 1. Stable workflow surface

- [x] 1.1 Remove pull-request and `main` push path filters from `openstock-ci`.
- [x] 1.2 Keep repository consistency, `vnalpha`, and `vnstock` as explicit jobs.
- [x] 1.3 Add an always-evaluated aggregate gate requiring all component results to be `success`.

## 2. Executable consistency and documentation

- [x] 2.1 Add repository checks for hidden/missing required gates.
- [x] 2.2 Add tests for stable checks, path-filter rejection and stale documentation.
- [x] 2.3 Replace obsolete branch-protection guidance with exact current checks, settings and bypass policy.

## 3. Validation

- [ ] 3.1 Run repository consistency, checker tests, full CI and package builds on the final PR SHA.
- [ ] 3.2 Record administrator verification of the active GitHub `main` ruleset in issue #147.
