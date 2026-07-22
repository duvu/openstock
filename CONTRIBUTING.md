# Contributing to OpenStock

OpenStock is developed spec-first. GitHub Issues define active scope and dependencies; OpenSpec defines behavior, design and implementation evidence for material changes.

## Development method

OpenStock does not require TDD, test-first coding or red–green–refactor.

```text
specify/understand the public contract
→ implement
→ inspect or smoke-check
→ add/update the authoritative test
→ run focused coding and test checks once
```

Do not add production abstractions, mocks or dependency seams only to make tests easier to write. Remove temporary exploratory tests, scripts and diagnostics before completion.

## Coding policy

[`CODING.md`](CODING.md) is the normative source.

Required principles:

- imports belong at module scope at the top of the file;
- no function-local, class-local, conditional or mid-file imports;
- order imports as standard library, third-party and project-local;
- no wildcard or unused imports;
- fix circular dependencies instead of hiding them with deferred imports;
- use Ruff formatting and conventional Python naming;
- add explicit types to public/application/provider/repository boundaries;
- prefer typed models and enums over free-form dictionaries and strings;
- keep functions focused, dependencies one-directional and runtime state explicit;
- catch specific exceptions and use logging in application/library code.

For touched Python files, run:

```bash
make lint-files PROJECT=vnalpha FILES="src/path/file.py tests/path/test_file.py"
```

Use `PROJECT=vnstock` for vnstock files.

## Testing policy

[`TESTING.md`](TESTING.md) is the normative source.

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
local_validation_command:
local_validation_result:
```

Do not report duplicate executions as additional evidence. Each authoritative test should run once per applicable local validation stage. Issue [#348](https://github.com/duvu/openstock/issues/348) owns consolidation of the legacy suite.
