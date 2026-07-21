# Agent notes for the OpenStock repository

OpenStock is one repository containing `vnalpha`, `vnstock`, OpenSpec, packaging and CI assets.

## Repository structure

| Path | Responsibility |
|---|---|
| `vnalpha/` | Research workspace, DuckDB pipeline, CLI/TUI, assistant and tests. |
| `vnstock/` | Provider-independent market-data library/service. |
| `openspec/` | Active changes, archive and accepted specifications. |
| `packaging/` | Package and deployment assets. |
| `.github/` | CI and release workflows. |
| `Makefile` | Repository commands. |

## Product boundary

OpenStock is research-only. Do not add broker login, order placement, account mutation, margin, transfers or autonomous trading execution. Deterministic application services own provisioning and mutation. Fresh warehouse and tool output outrank summaries and model prose.

## Development method: no TDD

OpenStock does **not** use test-driven development or a mandatory red–green–refactor workflow.

```text
understand or specify the public contract
→ implement the smallest complete change
→ inspect or smoke-check the behavior
→ add or update the single authoritative contract test
→ run the bounded development test once
```

- Do not write failing tests before implementation merely to satisfy process ceremony.
- Do not design production code around mocks or test-only seams.
- Tests validate stable externally observable behavior after the implementation shape is understood.
- Temporary diagnostics and exploratory tests must be removed before completion unless they become the single authoritative public or risk-contract test.
- Spec-first remains required for material changes; spec-first is not test-first.

## Development loop: hard limit 60 seconds

The inner edit-test loop MUST finish within 60 seconds.

```text
edit
→ lint only changed files when practical
→ run the single owning authoritative contract test
→ stop
```

```bash
make test-loop TEST=tests/path/to/test_file.py::test_contract
```

- Do not run `make test-vnalpha`, `verify-r0`, `verify-r4`, `verify-hardening`, package installation, research evals, repository-wide script checks or GitHub Actions after each patch.
- Do not rerun the same behavior through repository, service, CLI, TUI and assistant layers.
- If the selected test cannot finish within 60 seconds, treat that as test-architecture debt. Stop and report it instead of expanding the loop.
- Documentation-only changes require no runtime tests.
- OpenSpec-only changes require only the relevant strict validation when preparing the final candidate.
- Full component, package and release gates run only after the implementation candidate is frozen, and only once per final SHA.

## Minimal meaningful test policy

OpenStock optimizes for a **small set of meaningful contract tests**, not maximum test count, branch coverage or edge-case enumeration.

```text
one public feature, public function or independent risk contract
→ one authoritative automated test
```

Mandatory rules for agents:

1. **Test the public contract once.** Count externally observable contracts, not private helpers, branches, issue numbers, files or literal input values.
2. **Do not add tests for private helpers.** Exercise them through the owning public contract.
3. **Do not duplicate behavior across layers.** Domain/application services own behavior tests. CLI, TUI, assistant, repository and packaging receive tests only for distinct adapter or operational contracts.
4. **Use one table-driven test for equivalent cases.** Prefer a local case table and clear assertion messages over many `pytest.mark.parametrize` nodes.
5. **Do not add issue-specific regression files.** A bug fix updates or replaces the owning authoritative contract test after the fix is understood.
6. **Assert public outcomes, not implementation details.** Avoid call counts, private state, SQL text, helper ordering and mock choreography unless they are themselves the public contract.
7. **Mock only external boundaries.** Prefer real pure functions, in-memory DuckDB and small fakes over extensive internal mocking.
8. **Default to zero test growth.** For an existing contract, adding or strengthening coverage must merge, replace or delete obsolete tests so net test count is `<= 0`.
9. **A new public/risk contract may add at most one authoritative test.** Point-in-time exclusion, rollback, crash/lease recovery, writer exclusion, policy approval/rollback, security and package-state preservation may be separate risk contracts.
10. **Do not move duplicate tests to nightly.** Delete or consolidate them.
11. **Keep tests compact.** A normal contract test should usually be `<= 80` lines and a normal test file `<= 250` lines. Longer tests require a clearly independent operational risk contract.
12. **Do not add test infrastructure casually.** A new fixture, helper, checker or script must remove more duplicated code or execution than it introduces.

Repository budget:

```text
target: approximately 200 authoritative tests
hard cap: 250 authoritative tests
test LOC guidance: normally <= 0.8 × production LOC
```

The LOC ratio is a design warning, not a reason to compress unreadable assertions. Meaningful contract coverage outranks raw line counts.

Before completing a behavior-changing PR, report:

```text
contract_id:
authoritative_test:
tests_removed_or_merged:
net_test_count_change:
net_test_LOC_change:
```

An agent MUST NOT add a second authoritative test for an existing contract without explicitly replacing or deleting the previous owner.

Issue [#348](https://github.com/duvu/openstock/issues/348) owns consolidation and CI enforcement. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Implementation guidance

[`vnalpha/docs/common-implementation-failures.md`](vnalpha/docs/common-implementation-failures.md) is a reference catalogue, not mandatory reading for every task. Read only sections directly relevant to the changed contract or an observed failure. Do not load the full document into an agent context by default.

For implementation and review:

- verify runtime semantics rather than file or command presence;
- inspect real callable signatures and typed boundaries;
- preserve truthful statuses, evidence, remediation and fail-closed behavior;
- inspect every affected surface, but test shared behavior once at its owner;
- create a follow-up issue for intentionally deferred defects.

## OpenSpec workflow

- `openspec/active-changes.yaml` is the registry for non-archived changes.
- Search `openspec/changes/`, `openspec/changes/archive/` and `openspec/specs/` before creating a change.
- Update overlapping work instead of creating parallel remediation specs.
- Never mark tasks complete from prose alone; attach the evidence required by the task.

Relevant slash workflows when explicitly requested:

- `/opsx-propose` — create or revise proposal/design/tasks.
- `/opsx-apply` — implement an active change in dependency order.
- `/opsx-explore` — investigate without implementation.
- `/opsx-archive` — archive completed or superseded work and synchronize accepted specs.
