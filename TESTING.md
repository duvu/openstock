# OpenStock testing policy

This file is the normative source for automated testing in OpenStock.

## Goal

OpenStock optimizes for a **small, fast suite of meaningful contract tests**. Test count, branch coverage and edge-case enumeration are not quality goals.

Quality is provided by several layers together:

```text
clear public contracts
+ typed boundaries and schemas
+ runtime/database invariants
+ focused automated contract tests
+ bounded smoke checks
+ review and defect feedback
```

## Development method

OpenStock is spec-first for material changes, but it is not a TDD project.

```text
understand/specify contract
→ implement
→ inspect or smoke-check
→ add/update the authoritative test
→ run it once
```

Do not write failing tests before implementation as ceremony. Do not create production abstractions, mocks or dependency seams only for tests.

## Contract ownership

```text
one public feature, public function or independent risk contract
→ one authoritative automated test
```

A test must name the externally observable contract it protects. If no distinct public or risk contract can be identified, do not add the test.

Independent risk contracts may include:

- point-in-time and future-data exclusion;
- transaction rollback and atomicity;
- queue crash, lease and recovery semantics;
- warehouse writer exclusion;
- policy approval and rollback;
- security and research-only boundaries;
- package install, upgrade and state preservation.

## Test design rules

1. Test the owning public boundary once. Do not test private helpers, individual branches, issue numbers, files or literal values separately.
2. Domain/application services own behavior tests. CLI, TUI, assistant, repository and packaging receive separate tests only for distinct adapter or operational contracts.
3. Use one table-driven test for equivalent cases. Prefer a local case table with clear assertion messages over large `pytest.mark.parametrize` matrices.
4. Assert public output, persisted contract and critical side effects. Avoid private state, SQL text, call counts, helper order and mock choreography unless they are the contract.
5. Mock only external boundaries. Prefer real pure functions, temporary or in-memory DuckDB, deterministic clocks and small fakes.
6. Bug fixes update or replace the owning contract test. Do not create permanent issue-specific regression files.
7. Delete temporary exploratory tests, scripts and diagnostics before completion unless they become the authoritative test.
8. Do not move duplicate or obsolete tests to nightly. Merge or delete them.
9. A new fixture, helper, checker or test script must remove more duplication, runtime or maintenance cost than it introduces.

## Growth policy

For an existing contract:

```text
expected net test-count change <= 0
```

Strengthen, merge or replace its current authoritative test instead of adding another one.

For a new public or independent risk contract:

```text
maximum +1 authoritative test
```

A pull request must not introduce a second owner for an existing contract.

## Size and repository budget

```text
normal contract test: usually <= 80 LOC
normal test file: usually <= 250 LOC
repository target: 180–220 authoritative tests
repository hard cap: 250 authoritative tests
test LOC guidance: normally <= 0.8 × production LOC
```

These are design signals, not reasons to compress assertions into unreadable code. A justified concurrency, recovery or package contract may be longer.

## Quality without test proliferation

Prefer mechanisms that protect every execution rather than more sample tests:

- enums and typed result models instead of free-form strings and dictionaries;
- schema validation and database constraints;
- explicit point-in-time, date-ordering and state-transition invariants;
- exhaustive mappings for public statuses and actions;
- deterministic application services with narrow external boundaries;
- static analysis, lint and type checking where useful.

Periodically assess test effectiveness using sampled mutation checks and operational evidence, not raw coverage percentage. Track defect escapes, repeated bugs, flaky tests, diagnosis time and validation duration. Add a new risk contract only when evidence shows a distinct unprotected failure class.

## Validation lanes

### Development

```text
one owning authoritative test
hard limit: 60 seconds
```

Use:

```bash
make test-loop TEST=tests/path/to/test_file.py::test_contract
```

Do not run full suites, R0/R4, packaging, research evals, repository-wide checks or GitHub Actions after each patch.

### Pull request

Run changed-domain authoritative tests and relevant static checks. Target wall time: 5 minutes or less.

### Final merge candidate

Run the complete authoritative suite once on the frozen final SHA. Do not surround it with overlapping regression, R0 or R4 selections.

### Packaging/release

Run install, upgrade, rollback and operational acceptance only for packaging, installation, dependency-layout, service-unit or release changes.

## Required PR evidence

A behavior-changing pull request must state:

```text
contract_id:
authoritative_test:
tests_removed_or_merged:
net_test_count_change:
net_test_LOC_change:
validation_command:
```

Issue [#348](https://github.com/duvu/openstock/issues/348) owns consolidation of the legacy suite and enforcement of these limits.
