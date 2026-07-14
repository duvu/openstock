# OpenSpec governance

`openspec/changes/` contains only changes that still have unresolved product or implementation scope. Completed, superseded, duplicate, or conflicted changes belong under `openspec/changes/archive/`.

The machine-readable source of truth is [`active-changes.yaml`](active-changes.yaml).

## Review result (2026-07-14)

The 2026-07-11 reconciliation established the active execution set. Subsequent focused changes include `symbol-knowledge-memory`, `tui-terminal-rendering-integrity`, and the prioritized commercial-data change `fiinquantx-provider-integration`.

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
P0  fiinquantx-provider-integration
    documentation inventory (complete)
      → licensed runtime/commercial verification
      → optional synchronous provider foundation
      → reference and historical market data
      → flow/ownership/market structure/valuation
      → period-aware fundamentals
      → namespaced vendor analytics
    streaming requires a separate accepted change
    ↓
P1  prod-b-sandbox-mvp
    + tui-terminal-rendering-integrity
    ↓
P2  research-intelligence-data-model-foundation (completed; archived 2026-07-13)
    ↓
    symbol-knowledge-memory
    + prod-c-research-automation
    + remaining research-intelligence contracts
    ↓
P3  prod-d-closed-loop-repair + tui-research-workflow-polish
```

`fiinquantx-provider-integration` adds the first prioritized commercial provider to the `vnstock` plugin platform. The official package repository distributes wheels, while the detailed 125-page API documentation mirror is committed under `docs/fiinquant/site/` by PR #103. Documentation inventory is complete, but licensed runtime verification remains mandatory for exact return objects, field types, units, timestamps, access/entitlement, limits and commercial persistence rights.

The initial provider is synchronous and uses only the positive data-method allowlist through `PluginRuntime`. FiinQuantX realtime callbacks and order-book subscriptions require a separate streaming architecture. Every documented broker, account, funding, order, position, allocation and execution method is permanently outside scope under the **read-only research boundary**.

`tui-terminal-rendering-integrity` addresses GitHub issue #60. It defines surface-aware file-backed TUI logging, terminal-frame ownership, non-overlapping Textual regions, height-aware composer suggestions, bounded TODO content, and a fully contained LogScreen. It is intentionally separate from research artifact presentation and acts as a prerequisite for further `tui-research-workflow-polish` expansion.

`symbol-knowledge-memory` depends on the hardening and research-intelligence data-model contracts. Its core event/claim store, per-symbol Markdown card, explicit user-note workflow, compaction, and temporal retrieval may proceed independently of unfinished deep-symbol UI work; automatic ingestion adapters must consume only validated persisted artifacts.

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