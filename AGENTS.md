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
