# Agent notes for the OpenStock repository

OpenStock is a single Git repository containing two Python projects plus repository-level specifications, packaging, deployment, and validation assets.

## Repository structure

| Path | Responsibility |
|---|---|
| `vnalpha/` | Primary runnable research workspace: CLI, Textual TUI, assistant, deterministic tools, warehouse pipeline, evaluation, and tests. |
| `vnstock/` | Vietnamese market-data library/service used as a data provider. Keep it data-focused. |
| `openspec/` | Active changes, archived change history, and accepted capability specifications. |
| `packaging/` | Debian/package verification, deployment scripts, service assets, backup, and structural checks. |
| `.github/` | Repository CI and release gates. |
| `Makefile` | Authoritative cross-repository validation targets. |

Run component-specific commands from the relevant project directory when required, but use root Make targets for release and integration gates.

## Product boundary

The system is research-only. Do not add broker integration, order placement, account management, portfolio allocation, margin, transfers, or trading execution. Do not give the assistant unrestricted SQL, filesystem, shell, or code execution. The assistant must not autonomously call `data.fetch`; deterministic application services own data provisioning.

Fresh warehouse and tool output is authoritative over workspace summaries and model prose.

## Mandatory implementation playbook

Before implementing, reviewing, merging, or closing any OpenStock ticket, read:

- [`vnalpha/docs/common-implementation-failures.md`](vnalpha/docs/common-implementation-failures.md)

Use its mandatory checklist explicitly. In particular:

- verify runtime semantics rather than file or command presence;
- inspect real callable signatures and boundary types;
- inspect every affected CLI, TUI, assistant, legacy, readiness, and packaged path, but test shared domain behavior once at its owning public contract rather than repeating the same behavior matrix through every surface;
- preserve truthful `SUCCESS`/`PARTIAL`/`FAILED` and optional/required semantics;
- cover the complete fail-closed boundary, audit correlation, evidence, remediation, and backward compatibility through explicit public or risk contracts;
- do not infer that focused tests, local commands, or skipped CI gates prove completion;
- create and link a follow-up issue for intentionally deferred defects.

When a review reveals a new recurring failure pattern, update the playbook in the same change or its immediate follow-up.

## Authoritative test policy

OpenStock uses a **1:1 public-contract-to-authoritative-test policy**:

```text
one public feature, public function, or independent risk contract
→ one authoritative automated test
```

Apply the policy as follows:

- Count externally observable public contracts, not private helper functions, implementation branches, issue numbers, or source files.
- Do not create separate tests for private helpers when their behavior is already exercised through the owning public contract.
- One authoritative test may use table-driven cases and multiple assertions to cover equivalent inputs, edge conditions, and invariants without generating a large parameterized test matrix.
- Domain and application services own behavioral coverage. CLI, TUI, assistant, repository, and packaging layers receive separate tests only when they expose a distinct public adapter or operational contract.
- High-impact boundaries such as point-in-time exclusion, transaction rollback, queue crash recovery, lease recovery, writer exclusion, policy approval/rollback, security boundaries, and package state preservation are independent risk contracts. Each may own one authoritative test.
- A bug fix should update or replace the authoritative test for the owning contract. Do not normally retain permanent issue-specific regression files in parallel with the contract test.
- Adding an authoritative test requires a new public/risk contract or the replacement of an obsolete test. Identify the contract ID and remove or merge duplicate coverage in the same change where practical.
- Do not preserve duplicate or obsolete tests by moving them to another required or nightly suite.
- Required validation should execute each authoritative test once per applicable lane; do not run overlapping R0, regression, R4, and full-suite selections sequentially.

Repository budget:

```text
target: approximately 200 authoritative automated tests
hard cap: 250 authoritative automated tests
```

Issue [#348](https://github.com/duvu/openstock/issues/348) owns consolidation of the existing suite, the authoritative contract manifest, and CI enforcement. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for contributor-facing rules.

## OpenSpec workflow

- `openspec/active-changes.yaml` is the authoritative registry for non-archived changes.
- `openspec/changes/` contains only unresolved active/partial/planned work.
- `openspec/changes/archive/` preserves completed, superseded, duplicate, abandoned, or conflicted changes.
- `openspec/specs/` contains accepted implemented capability contracts.
- Search all three locations before creating a new change. Update overlapping active work instead of adding another remediation/closure spec.
- Never mark tasks complete from prose alone; use the evidence required by each task.
- `openstock-four-phase-hardening` is completed and archived; its accepted hardening contract remains the prerequisite baseline for later sandbox, automation, persistence, and TUI expansion.

Relevant slash workflows when explicitly requested:

- `/opsx-propose` — create or revise a change proposal/design/tasks.
- `/opsx-apply` — implement an active change in dependency order.
- `/opsx-explore` — investigate without implementation.
- `/opsx-archive` — archive a completed or superseded change and synchronize accepted specs.
