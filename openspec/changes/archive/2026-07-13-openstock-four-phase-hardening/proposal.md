# Proposal: OpenStock four-phase hardening

## Summary

Implement a coordinated hardening program for the current OpenStock/vnalpha codebase across four ordered phases:

```text
Phase 1 — Repository and data safety
Phase 2 — Context trust and assistant lifecycle
Phase 3 — Runtime correctness
Phase 4 — CI, evaluation, and release governance
```

The objective is to remove known P0/P1 risks before adding more research engines or agentic workflows. This change is not a cosmetic cleanup. It must close data-leakage, concurrency, lifecycle, trust-boundary, correctness, packaging, and validation gaps with executable tests and evidence.

This OpenSpec is an implementation contract. Runtime work belongs in a follow-up implementation PR or a sequence of implementation PRs that follow the dependency order in `execution.md` and `tasks.md`.

## Current state

The codebase already has substantial capabilities:

```text
- modular CLI entrypoint
- TUI with one composer, one output stream, responsive TODO rail, and status bar
- workspace context lifecycle
- deterministic data provisioning
- central tool policy
- model routing profiles and fallbacks
- warehouse-grounded research tools
- groundedness and research-language policy checks
- research answer audit records
- deterministic golden-set evaluation framework
```

The current implementation also contains material risks:

```text
- local runtime workspaces, generated metadata, and worktree gitlinks are tracked in Git
- workspace locking is not mutually exclusive and mutations are not transactional
- archived workspaces can become the latest active workspace
- workspace roots depend on the current working directory
- workspace context is concatenated into the user prompt at the same trust level
- raw prefixed prompts can be persisted even when raw storage is disabled
- natural-language turns classify and build plans more than once
- approved plans are rebuilt instead of executing the exact approved plan
- TUI can record a request that was rejected because another request was busy
- corrupt workspace state can block TUI startup
- data-ensure locking is not atomic
- invalid dates can silently become today's date
- data-ensure cache hits do not verify all supporting artifacts
- shortlist lineage can claim sector artifacts that do not exist
- compaction writes a summary but does not reduce retained context
- golden evaluation checks static fixtures but does not replay production orchestration
- golden fixtures may not be included in built distributions
- golden evaluation is not a required root CI gate
- implementation can be merged while OpenSpec validation remains incomplete
```

## Problem statement

The system is adding product capability faster than it is closing architecture and operational risks. Continuing to add deep-analysis, shortlist persistence, scenario planning, or autonomous workflows before hardening the foundation would increase migration cost and make failures harder to diagnose.

The desired state is:

```text
Repository is free of runtime/generated/user-state artifacts.
Workspace mutations are atomic, bounded, redaction-aware, and lifecycle-correct.
Historical workspace context is untrusted auxiliary data, not part of the current user instruction.
Each assistant turn is classified and planned once, then executes the exact prepared plan.
Invalid inputs fail explicitly; cache hits and lineage are evidence-based.
CI proves lint, tests, R4, packaging, golden fixtures, runtime replay, and repository hygiene before merge.
OpenSpec task completion always matches attached validation evidence.
```

## Goals

### Phase 1 — Repository and data safety

- Remove committed `.vnalpha/`, `vnalpha/.vnalpha/`, `.worktrees/`, egg-info, caches, and other runtime/generated artifacts from Git tracking.
- Add ignore rules and a repository-hygiene verifier that prevents recurrence.
- Scan repository history and current files for secrets and sensitive workspace content.
- Define one deterministic workspace root policy independent of the shell working directory.
- Implement atomic workspace lock acquisition and transactional read-modify-write mutations.
- Correct active/archive/latest/resume semantics.
- Bound retained workspace inputs, warnings, errors, events, artifacts, and completed tasks.
- Apply redaction consistently to all persisted workspace text.
- Export a redacted projection without leaking absolute local paths.

### Phase 2 — Context trust and assistant lifecycle

- Keep the current user request separate from workspace and chat context.
- Mark workspace/chat context as untrusted historical context in a lower-trust message.
- Run safety checks and intent classification against the current request only.
- Make `store_raw` control prompt persistence in practice.
- Add prepared-turn APIs that classify and build a plan once.
- Execute the exact immutable plan that was previewed or approved.
- Remove double classification and double planning from auto-execute and approval flows.
- Make workspace recording best-effort and prevent workspace failures from blocking TUI operation.
- Reject or label busy submissions before they enter workspace history.
- Add recovery behavior for corrupt or inaccessible workspace state.

### Phase 3 — Runtime correctness

- Make data-ensure lock acquisition atomic and owner-aware.
- Reject invalid dates rather than silently substituting today's date.
- Strengthen data-ensure cache-hit eligibility with canonical, benchmark, feature, freshness, quality, and lineage checks.
- Ensure artifact references are emitted only for persisted artifacts that actually exist.
- Convert workspace compaction into real retention reduction with archive evidence.
- Resolve command namespace ambiguity such as `/new`.
- Emit TODO visibility events only on real transitions.
- Scope model overrides to the correct session/workspace rather than a process-global implicit session.
- Preserve accurate source-reference semantics in synthesized research answers.

### Phase 4 — CI, evaluation, and release governance

- Make lint pass on the latest branch and keep it required.
- Add root Make targets for research evaluation and repository hygiene.
- Package golden fixtures as package resources or installable data.
- Add runtime-replay evaluation through production classifier/planner/executor/synthesizer boundaries using deterministic fakes.
- Run fixture-contract and runtime-replay evaluation in CI.
- Require focused tests, full tests, R4, packaging verification, evals, hygiene, and secret scanning before merge.
- Reconcile OpenSpec task state with actual command evidence.
- Document branch-protection requirements and release gates.

## Non-goals

- No broker, account, order, allocation, margin, or execution functionality.
- No personalized financial advice.
- No rewrite of the warehouse or TUI framework.
- No migration to a remote workspace service.
- No live provider calls in deterministic evaluation.
- No deletion or rewriting of Git history without an explicit, separately reviewed operational decision.
- No claim that future deep-analysis or scenario engines are complete because hardening is complete.

## Design principles

### Safety before convenience

Destructive cleanup, raw export, or context persistence must require explicit policy. Safe defaults are mandatory.

### One source of truth

Workspace activation, assistant plan execution, artifact lineage, and CI completion must each have a single canonical state transition or policy source.

### Fail explicitly

Invalid dates, corrupt context, missing artifacts, failed audits, and incomplete validation must not be silently translated into success.

### Deterministic boundaries

The LLM may explain deterministic outputs. It must not control lock acquisition, lifecycle transitions, cache eligibility, artifact existence, validation gates, or plan mutation.

### Evidence-backed completion

A checked task must point to code, a test, a command result, or a committed validation artifact. A merged PR is not itself proof that the task is complete.

## Implementation strategy

The work SHALL be implemented in phase order. A later phase may begin only when its required predecessor gate passes, except for isolated documentation or test preparation that cannot alter runtime behavior.

Recommended PR slicing:

```text
PR A: Phase 1 repository/workspace safety
PR B: Phase 2 context trust and prepared-turn lifecycle
PR C: Phase 3 correctness hardening
PR D: Phase 4 CI/evaluation/release gates
```

A single implementation PR is allowed only if it preserves reviewability and each phase has independent commits, tests, and validation evidence.

## Success criteria

This program is complete only when all of the following are true:

```text
- no runtime workspace, generated package metadata, cache, or worktree gitlink is tracked
- repository-hygiene and secret checks fail on recurrence
- workspace root is deterministic
- every workspace mutation uses an atomic transaction lock
- archived workspaces cannot become latest without explicit reactivation
- context retention is bounded and compaction reduces retained state
- export is redacted and path-safe
- current user input is separated from untrusted historical context
- safety/classification operate on the current request only
- raw prompt storage obeys configuration
- each turn is classified/planned once and exact approved plans are executed
- TUI remains usable when workspace state is corrupt or unavailable
- data locks, date validation, cache hits, and artifact references are correct
- model overrides are session/workspace scoped correctly
- fixture-contract and runtime-replay evaluation pass from an installed package
- CI requires lint, tests, R4, verify, eval, hygiene, and secret checks
- all OpenSpec tasks are checked only with attached command evidence
```

## Completion principle

Do not mark this change complete because code moved, a PR merged, or local manual testing appeared successful. Completion requires every phase gate in `validation.md` to pass and every non-deferred task in `tasks.md` to have evidence.