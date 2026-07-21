# Contributing to OpenStock

OpenStock is developed spec-first. GitHub Issues define active scope and dependencies; OpenSpec defines behavior, design and implementation evidence for material changes.

## Development method

OpenStock does not require TDD, test-first coding or red–green–refactor.

```text
specify/understand the public contract
→ implement
→ inspect or smoke-check
→ add/update the authoritative test
→ run it once
```

Do not add production abstractions, mocks or dependency seams only to make tests easier to write. Remove temporary exploratory tests, scripts and diagnostics before completion.

## Testing policy

[`TESTING.md`](TESTING.md) is the normative source. The required principles are:

```text
one public feature, public function or independent risk contract
→ one authoritative automated test
```

- Test externally observable behavior at its owning boundary.
- Do not test private helpers, individual branches, issue numbers or the same behavior across multiple layers.
- Use one table-driven test for equivalent inputs and edge cases.
- Existing contract: expected net test-count change `<= 0`.
- New public/risk contract: maximum `+1` authoritative test.
- Merge or delete duplicate tests; do not move them to nightly.
- A test that cannot be mapped to a distinct contract must not be added.
- Development feedback must use one owning test and finish within 60 seconds.

Repository guidance:

```text
normal contract test: usually <= 80 LOC
normal test file: usually <= 250 LOC
repository target: 180–220 authoritative tests
repository hard cap: 250 authoritative tests
test LOC guidance: normally <= 0.8 × production LOC
```

These are design signals, not incentives to make assertions unreadable. Quality also depends on typed boundaries, schemas, runtime/database invariants, review and defect feedback—not test count alone.

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

Do not report duplicate executions as additional evidence. Each authoritative test should run once per applicable validation lane. Issue [#348](https://github.com/duvu/openstock/issues/348) owns consolidation of the legacy suite and enforcement of these limits.
