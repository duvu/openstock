# Contributing to OpenStock

OpenStock is developed spec-first. GitHub Issues define active scope and dependencies; OpenSpec defines behavior, design and implementation evidence for material changes.

## Test policy: 1:1

The repository uses a **1:1 public feature/function-to-authoritative-test policy**:

```text
one public feature or public function
→ one authoritative automated test case
```

This is a contract-to-test ratio. It is not a line-coverage target and it does not require tests for private helper functions.

### Rules

1. Test externally observable behavior at the owning public boundary.
2. Do not create separate tests for private helpers, internal branches or issue numbers when the behavior is already covered by the public feature/function test.
3. One authoritative test may use table-driven assertions to exercise equivalent inputs and important edge conditions without creating many collected test nodes.
4. Do not repeat the same domain behavior through repository, service, CLI, TUI and assistant layers. The domain/application contract owns the behavior test; a surface receives a separate test only when it exposes a distinct public function or adapter contract.
5. High-impact boundaries such as point-in-time exclusion, transaction rollback, queue crash recovery, writer exclusion, policy approval and package state preservation are modeled as separate public risk contracts. Each such contract may own one test.
6. A new authoritative test requires one of:
   - a new public feature/function contract;
   - a newly identified independent risk contract;
   - replacement of an obsolete authoritative test.
7. Bug fixes update or replace the owning contract test. Do not normally add permanent issue-specific regression files.
8. Equivalent parameter combinations must not be expanded solely to increase test counts.

## Test budget

The repository target is approximately **200 authoritative automated tests** with a hard cap of **250** across `vnalpha`, `vnstock`, packaging, governance and end-to-end validation.

Issue [#348](https://github.com/duvu/openstock/issues/348) owns consolidation of the existing suite and CI enforcement of this budget.

## Pull request expectations

A pull request that adds or changes behavior must identify:

- the public feature/function or risk contract being changed;
- the one authoritative test that owns the contract;
- obsolete or duplicate tests removed or replaced;
- exact validation commands and results for the final SHA.

Do not report duplicated test executions as additional evidence. Required validation should execute each authoritative test once per applicable lane.
