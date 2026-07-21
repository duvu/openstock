# Contributing to OpenStock

OpenStock is developed spec-first. GitHub Issues define active scope and dependencies; OpenSpec defines behavior, design and implementation evidence for material changes.

## Development method: implementation first, tests after

OpenStock does **not** require test-driven development, test-first coding or red–green–refactor.

```text
specify or understand the public contract
→ implement the complete behavior
→ inspect or smoke-check the result
→ add or update one authoritative automated test
→ run that test once
```

- Do not create a failing test before implementation solely as process ceremony.
- Do not add production abstractions, mocks or dependency seams only to make tests easier to write.
- Tests validate stable externally observable behavior after the implementation and failure model are understood.
- Temporary exploratory tests, scripts and diagnostics must be removed before completion unless they become the one authoritative contract test.

## Minimal meaningful test policy

The repository uses a **1:1 public-contract-to-authoritative-test policy**:

```text
one public feature, public function or independent risk contract
→ one authoritative automated test
```

The goal is not high test count. The goal is a small suite where each test protects a meaningful externally observable contract.

### Rules

1. Test behavior at the owning public boundary, not every private helper, branch, issue or file.
2. Do not duplicate the same domain behavior through repository, service, CLI, TUI and assistant layers.
3. Use one table-driven test for equivalent inputs and edge cases instead of expanding large parameterized matrices.
4. Assert public output, persisted contract and critical side effects; avoid private state, helper call order and mock choreography.
5. Mock only external boundaries. Prefer real pure functions, in-memory DuckDB and small fakes.
6. A bug fix updates or replaces the owning contract test. Do not normally add permanent issue-specific regression files.
7. For an existing contract, the default expected net test-count change is `<= 0`.
8. A new public or independent risk contract may add at most one authoritative test.
9. Duplicate or obsolete tests must be merged or deleted, not moved to nightly.
10. A new fixture, helper, checker or test script must remove more duplication or runtime than it introduces.
11. If a proposed test cannot be mapped to a distinct public or risk contract, it must not be added.

High-impact boundaries such as point-in-time exclusion, transaction rollback, queue crash/lease recovery, writer exclusion, policy approval/rollback, security and package-state preservation may be modeled as independent risk contracts. Each such contract still owns only one authoritative test.

## Test size and repository budget

Guidance:

```text
normal contract test: usually <= 80 LOC
normal test file: usually <= 250 LOC
repository target: approximately 200 authoritative tests
repository hard cap: 250 authoritative tests
test LOC: normally <= 0.8 × production LOC
```

These are design signals, not incentives to make assertions unreadable. A justified concurrency, recovery or package contract may be longer.

Issue [#348](https://github.com/duvu/openstock/issues/348) owns consolidation and CI enforcement.

## Pull request expectations

A behavior-changing pull request must state:

```text
contract_id:
authoritative_test:
tests_removed_or_merged:
net_test_count_change:
net_test_LOC_change:
validation_command:
```

A new test for an existing contract must replace or delete the previous owner. Do not report duplicated executions as additional evidence. Each authoritative test should run once per applicable validation lane.
