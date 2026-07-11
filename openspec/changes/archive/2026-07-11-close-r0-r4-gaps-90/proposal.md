# Proposal: Close R0-R4 gaps to >90% completion

## Summary

Add a focused OpenSpec change to close the remaining implementation, verification, and integration gaps that prevent OpenStock R0-R4 from being declared more than 90% complete.

This change does **not** re-spec the full R0-R4 roadmap. It targets the remaining blockers observed after the latest codebase review:

```text
R0 — deterministic pipeline mostly works, but needs stronger service-backed proof and regression coverage.
R1 — architecture docs exist, but must be aligned to actual deployable files and validation evidence.
R2 — deploy/verify scaffolding exists, but runtime proof and several deploy correctness issues remain.
R3 — TUI shell exists, but needs integration/pilot coverage and tighter workspace behavior proof.
R4 — ChatController exists, but ChatPanel still bypasses it; persistence/safety/trace wiring is incomplete.
```

## Current review result

Approximate current state from repository inspection:

```text
R0 — Core pipeline:              85-90%
R1 — Architecture alignment:     80-85%
R2 — Deploy & verify:            65-75%
R3 — Terminal workspace:         70-80%
R4 — Chat workspace:             50-60% end-to-end, despite stronger backend/controller work
```

Target after this change is implemented and validated:

```text
R0 >= 92%
R1 >= 92%
R2 >= 90%
R3 >= 90%
R4 >= 90%
```

## Why

Recent implementation work has closed many earlier gaps: command alignment, feature metadata, outcome evaluation, systemd wrappers, post-deploy verification, backup, TUI ContentSwitcher layout, ChatController, plan modes, and chat safety helpers.

However, several blockers still prevent a reliable MVP closure:

1. ChatPanel still owns a separate command/assistant dispatch path instead of delegating to ChatController.
2. Chat transcript persistence is not yet guaranteed for every user, assistant, command, plan, trace, and local-command turn.
3. `/clear` semantics are inconsistent with audit-preserving transcript behavior.
4. Hard-denied planned tools can still be treated as pending approval unless every plan step is permission-evaluated before pending storage.
5. The daily systemd pipeline calls `sync ohlcv --universe VNINDEX`; benchmark sync must use `sync index --symbol VNINDEX`.
6. The systemd writer lock is not sufficient if the lock is only taken in `ExecStartPre`; the lock must span the entire pipeline.
7. R2 has deploy scaffolding but lacks an auditable fresh-host validation report.
8. CI-safe verification skips too many deploy correctness checks instead of validating compose config, scripts, packaging metadata, and safe static properties.
9. TUI tests remain mostly import/smoke-level and do not prove the terminal analyst flow.
10. Completion status is not yet tied to reproducible evidence.

## Goals

- Close the remaining R0-R4 blockers through implementation requirements and validation gates.
- Preserve the local-first, terminal-first, research-only direction.
- Convert R2 from deploy scaffolding into deployable proof.
- Make ChatController the single orchestration path for ChatPanel.
- Make chat persistence auditable and deterministic.
- Make hard-deny policy impossible to bypass through natural language, slash commands, local commands, or planned tool calls.
- Add evidence-backed completion metrics for each phase.

## Non-goals

- No broker integration.
- No order placement.
- No account, portfolio, margin, transfer, or trading execution feature.
- No public web service exposure.
- No R5 local runtime/server dependency.
- No production multi-user deployment.
- No ML model/ranking lab.
- No general-purpose shell, SQL, Python, web, MCP, or filesystem agent surface.

## Scope

### R0 gap closure

- Add service-backed smoke proof for the CLI pipeline.
- Strengthen migration upgrade tests.
- Add feature metadata and stale/missing benchmark regression tests.
- Add Makefile/CI targets for reproducible pipeline checks.

### R1 gap closure

- Align architecture/runbook docs to actual implemented files.
- Add a phase completion evidence matrix.
- Explicitly document what remains deferred to R5+.

### R2 gap closure

- Fix benchmark sync in systemd pipeline.
- Replace fragile `ExecStartPre` locking with a lock that spans the entire pipeline.
- Add `openstock-run-pipeline` or equivalent wrapper.
- Strengthen `openstock-verify --ci` to validate static deployment correctness.
- Add package build/install verification gates.
- Add fresh-host validation report.

### R3 gap closure

- Add Textual pilot/integration smoke tests for workspace navigation.
- Prove watchlist/detail/quality/rejected/outcomes/chat surfaces do not crash on empty warehouse.
- Prove ChatPanel remains persistent while switching main workspace screens.

### R4 gap closure

- Wire ChatPanel to ChatController.
- Remove ChatPanel-owned command registry/parser/assistant dispatch paths.
- Persist every chat turn and link relevant sessions/traces/plans.
- Fix `/clear` to preserve audit history unless an explicit destructive path is used.
- Apply hard-deny permission evaluation before plan storage or approval.
- Persist trace timeline events and make `/trace` reflect real events.

## Success criteria

This change is complete only when the following are true:

```text
make test-vnalpha                                       passes
make lint-vnalpha                                       passes or explicit exceptions are documented
make verify-r0                                          passes
make verify-r2-ci                                       passes
docker compose config                                   passes
openstock-verify --ci                                   passes
openstock-run-pipeline --ci-fixture or equivalent       passes
openstock-verify                                        passes on a deployed host
openstock-backup-warehouse                              passes on a deployed host
vnalpha.deb build/install verification                  passes or package task is explicitly deferred with justification
TUI pilot/integration tests                             pass
ChatPanel -> ChatController integration tests            pass
Chat persistence/trace/plan/hard-deny tests              pass
fresh-host validation report                             committed or linked
phase completion matrix                                  shows R0-R4 >= 90% with evidence
```

## Completion principle

Do not mark tasks complete because an OpenSpec checkbox says so. A task is complete only when supported by one of:

- implemented code;
- automated test;
- runnable script;
- CI log;
- local validation log;
- fresh-host validation report;
- updated documentation that matches the actual executable behavior.
