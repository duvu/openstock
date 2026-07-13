# Execution guide: OpenStock four-phase hardening

## Purpose

This guide is written for both human developers and coding agents. It defines how to select work, implement it, prove it, and hand it off without losing state or falsely claiming completion.

The source of truth is the repository state, not chat history.

## Required reading order

Before implementation, read:

```text
1. proposal.md
2. review.md
3. design.md
4. tasks.md
5. specs/openstock-four-phase-hardening/spec.md
6. validation.md
7. current runtime code and tests for the selected task
```

Do not implement from `tasks.md` alone. The normative scenarios in the spec and the architectural constraints in `design.md` also apply.

## Phase dependency graph

```text
Phase 1A repository cleanup
        ↓
Phase 1B workspace root + locking + lifecycle
        ↓
Phase 1C retention + redaction + export
        ↓
PHASE 1 GATE
        ↓
Phase 2A context trust separation
        ↓
Phase 2B prompt persistence
        ↓
Phase 2C prepared-turn lifecycle
        ↓
Phase 2D TUI resilience
        ↓
PHASE 2 GATE
        ↓
Phase 3A data lock/date/cache
Phase 3B artifact refs/compaction/commands
Phase 3C model/source-ref correctness
        ↓
PHASE 3 GATE
        ↓
Phase 4A packaging and Make targets
Phase 4B runtime replay evaluation
Phase 4C CI and OpenSpec verification
        ↓
FINAL GATE
```

Tasks within the same horizontal group may run in parallel only if their files and runtime contracts do not overlap.

## Branch and PR strategy

Preferred implementation branches:

```text
agent/hardening-phase-1-repository-workspace
agent/hardening-phase-2-context-lifecycle
agent/hardening-phase-3-correctness
agent/hardening-phase-4-ci-evaluation
```

Each PR should contain:

```text
- one coherent phase or independently reviewable subphase
- code and tests together
- updated tasks.md checkboxes only for proven work
- updated validation.md evidence
- migration and rollback notes
```

Do not mix unrelated research-feature work into hardening PRs.

## Task selection algorithm

A human or agent should select work using this deterministic procedure:

```text
1. Find the first phase whose gate is not complete.
2. Within that phase, find the lowest-numbered unchecked task whose dependencies are complete.
3. Review current code; confirm the finding still exists.
4. If the finding no longer exists, add evidence and a regression test before checking the task.
5. Implement the smallest vertical slice that reaches an observable acceptance scenario.
6. Run focused tests.
7. Fix failures.
8. Run the phase gate when all tasks in the phase are complete.
9. Record exact evidence in validation.md.
10. Commit the slice.
```

Do not skip to a later phase because it appears easier.

## Task metadata convention

Each task in `tasks.md` uses this notation where relevant:

```text
[depends: task IDs]
[files: expected file areas]
[evidence: expected tests/commands]
```

These annotations are guidance, not permission to ignore other affected files.

## Definition of done for one task

A task may be changed from `[ ]` to `[x]` only when all applicable conditions are true:

```text
- runtime implementation exists or the finding is proven absent
- focused test exists and passes
- public behavior is documented when changed
- migration/backward compatibility is handled
- observability is updated when the task changes an operational state
- validation.md contains evidence reference
- no known P0/P1 defect remains inside that task's scope
```

A code review comment, merged PR, or manually observed behavior is not sufficient by itself.

## Evidence format

For every executed command, append a row to `validation.md`:

```text
| UTC timestamp | commit SHA | phase/task | command | exit | result summary | evidence artifact |
```

Example:

```text
| 2026-07-12T04:00:00Z | abc1234 | 1.12 | pytest -q tests/workspace_context/test_locking.py | 0 | 12 passed | CI run 123/job 456 |
```

If a command cannot run, record:

```text
BLOCKED
exact command
exact reason
owner or external dependency
safe independent work that remains
```

Never mark the corresponding validation task complete.

## Deferred task format

A task may be deferred only with an explicit entry:

```text
DEFERRED: <reason>
Owner: <person/team>
Dependency: <issue/PR/spec>
Risk accepted until: <date or milestone>
```

A generic “future work” note is not sufficient.

## Implementation rules by phase

### Phase 1 rules

```text
- Create backups before workspace schema migration or quarantine.
- Do not delete local operator workspace content merely to clean Git tracking.
- Do not rewrite Git history automatically.
- All state mutation tests must include concurrency or lost-update coverage.
- Safe defaults: dry-run clean, redacted export, no history export.
```

### Phase 2 rules

```text
- Current request remains a separate string/message at every layer.
- Historical context must be labeled untrusted.
- Classifier and safety tests must prove context instructions cannot change current intent.
- The approved plan object/hash is the object executed.
- No second classifier/planner call is allowed in approval or auto-execute tests.
```

### Phase 3 rules

```text
- Invalid explicit input fails before mutation.
- Cache-hit tests must include orphan/stale support artifacts.
- Artifact refs must be backed by query evidence.
- Lock tests use multiple processes where supported.
- Compatibility wrappers may remain but must delegate to corrected behavior.
```

### Phase 4 rules

```text
- Evaluation remains offline and deterministic.
- Runtime replay must exercise production interfaces, not duplicate their logic.
- Installed-package tests must not depend on repository-relative paths.
- CI must fail closed when a required check is absent.
- OpenSpec tasks cannot be auto-checked without command evidence.
```

## Commit convention

Suggested commit sequence:

```text
fix(repo): remove tracked runtime artifacts
feat(workspace): add transactional locking
fix(workspace): correct active archive lifecycle
feat(workspace): enforce retention and safe export
refactor(assistant): separate untrusted context
feat(assistant): add prepared turn execution
fix(tui): make workspace hooks resilient
fix(data): harden ensure lock date and cache
fix(research): verify artifact references
feat(evals): add runtime replay and packaged corpus
ci: require hardening and openspec gates
```

Keep commits independently understandable.

## Review checklist

Reviewer should verify:

```text
- Does code implement the exact task rather than only updating docs?
- Does the test fail on old behavior?
- Is the default behavior safer?
- Is state transition ownership explicit?
- Does any new path duplicate raw prompts or sensitive text?
- Does a compatibility wrapper hide an unresolved defect?
- Is validation evidence attached to the tested commit?
- Are tasks checked consistently with validation.md?
```

## Agent continuation protocol

When an agent stops or context becomes large, it must leave the repository in a resumable state:

```text
- commit stable work
- update validation.md
- leave incomplete tasks unchecked
- add a short “Next executable task” note in validation.md
- do not promise background work
```

A new agent should be able to continue using only repository files and Git history.

## Final completion protocol

Before declaring the OpenSpec complete:

```text
1. Run every command in the final validation matrix.
2. Run scripts/check-openspec-completion.py for this change.
3. Confirm no denied tracked paths or gitlinks.
4. Confirm no open P0/P1 finding in review.md remains without an approved defer record.
5. Confirm tasks.md has no unchecked non-deferred task.
6. Confirm validation.md contains evidence for the final commit SHA.
7. Confirm required GitHub checks pass.
8. Only then mark the change ready to archive.
```