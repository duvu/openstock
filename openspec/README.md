# OpenSpec governance

`openspec/changes/` contains only changes that still have unresolved product or implementation scope. Completed, superseded, duplicate, or conflicted changes belong under `openspec/changes/archive/`.

The machine-readable source of truth is [`active-changes.yaml`](active-changes.yaml).

## Review result (2026-07-11)

The review started with 14 non-archived changes and reduced the active set to 10.

### Archived during reconciliation

| Change | Disposition | Reason |
|---|---|---|
| `architecture-gap-remediation` | Superseded/conflicted | Duplicated the implemented architecture refactor, conflicted with accepted package paths, and was subsumed by four-phase hardening. |
| `assistant-research-intelligence-tools` | Implemented | Runtime capability merged in PRs #40/#42; residual repository-wide validation moved to four-phase hardening. |
| `model-routing-profiles` | Implemented | Runtime capability merged in PRs #37/#38; residual validation moved to four-phase hardening. |
| `prod-a-control-plane` | Implemented | Main contains the accepted control-plane behavior; residual broad gates moved to four-phase hardening. |

Archiving preserves the complete proposal/design/task/validation history. Implemented delta specs are synchronized to `openspec/specs/`; superseded/conflicted deltas are not promoted to the main spec set.

## Active execution order

```text
P0  openstock-four-phase-hardening
    ↓
P1  prod-b-sandbox-mvp
    ↓
P2  prod-c-research-automation + remaining research-intelligence contracts
    ↓
P3  prod-d-closed-loop-repair + tui-research-workflow-polish
```

Partial research-intelligence changes may retain already-implemented tool/intent slices, but new persistence, commands, and UI contracts must not bypass the P0 hardening gates.

## Reconciliation rules

1. Search `openspec/changes`, `openspec/changes/archive`, and `openspec/specs` before creating a new change.
2. Update an existing active change when scope overlaps; do not create a second closure/remediation change for the same capability.
3. Every active change must declare status, priority, dependencies, current evidence, and remaining scope.
4. Do not check a task from PR prose alone. A checked task requires code plus the evidence requested by that task.
5. Archive a change when it is completed, superseded, duplicate, abandoned, or incompatible with an accepted design.
6. Sync only accepted implemented requirements into `openspec/specs`; do not promote a superseded/conflicted delta.
7. Preserve the read-only research boundary: no broker, order placement, account management, portfolio allocation, margin, transfer, or trading execution.
8. The assistant must not gain unrestricted SQL, filesystem, shell, or code execution, and must not autonomously call `data.fetch`.
