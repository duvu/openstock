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

The required order is:

```text
understand or specify the public contract
→ implement the smallest complete change
→ inspect or smoke-check the behavior
→ add or update the single authoritative contract test
→ run the bounded development test once
```

Rules:

- Do not write failing tests before implementation merely to satisfy TDD ceremony.
- Do not design production code around mocks or test-only seams.
- Tests validate stable externally observable behavior after the implementation shape is understood.
- A bug fix updates the owning authoritative contract test after the root cause and fix are established.
- Exploratory implementation may use manual commands, logs, fixtures or temporary diagnostics before the final automated test is written.
- Temporary diagnostics and exploratory tests must be removed before completion unless they represent the one authoritative public or risk contract.
- Spec-first remains required for material changes; spec-first is not test-first.

## Development loop: hard limit 60 seconds

The inner edit-test loop MUST finish within 60 seconds.

```text
edit
→ lint only changed files when practical
→ run the single owning authoritative contract test
→ stop
```

Use:

```bash
make test-loop TEST=tests/path/to/test_file.py::test_contract
```

Rules:

- Do not run `make test-vnalpha`, `verify-r0`, `verify-r4`, `verify-hardening`, package installation, research evals, repository-wide script checks or GitHub Actions after each patch.
- Do not rerun the same test through repository, service, CLI, TUI and assistant layers.
- If the selected test cannot finish within 60 seconds, treat that as test-architecture debt. Stop and report it instead of expanding the loop.
- Documentation-only changes require no runtime tests.
- OpenSpec-only changes require only the relevant strict OpenSpec validation when preparing the final candidate, not after every edit.
- Full component, package and release gates run only after the implementation candidate is frozen, and only once per final SHA.
- Package install/upgrade/rollback checks run only for packaging, installation, dependency-layout or release changes.

## Authoritative test policy

OpenStock uses a 1:1 public-contract-to-authoritative-test policy:

```text
one public feature, public function or independent risk contract
→ one authoritative automated test
```

- Count externally observable contracts, not private helpers, branches, issue numbers or files.
- One authoritative test may use table-driven cases and multiple assertions.
- Domain/application services own behavior tests. Surfaces receive a separate test only for a distinct adapter contract.
- Point-in-time exclusion, transaction rollback, crash/lease recovery, writer exclusion, policy approval/rollback, security and package-state preservation may be independent risk contracts.
- A bug fix updates or replaces the owning contract test; do not accumulate permanent issue-specific regression tests.
- Adding a test requires a new contract or replacement of obsolete coverage.
- Do not move duplicate tests to nightly as a substitute for deleting them.

Repository budget:

```text
target: approximately 200 authoritative tests
hard cap: 250 authoritative tests
```

Issue [#348](https://github.com/duvu/openstock/issues/348) owns consolidation and CI enforcement. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Implementation guidance

[`vnalpha/docs/common-implementation-failures.md`](vnalpha/docs/common-implementation-failures.md) is a reference catalogue, not mandatory reading for every task. Read only the sections directly relevant to the changed contract or an observed failure. Do not load the full document into an agent context by default.

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
