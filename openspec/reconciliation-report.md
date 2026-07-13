# OpenSpec task/evidence reconciliation

Recorded 2026-07-12 against the shared working tree.

## Inventory

| Location | Changes | With validation ledger | Decision |
|---|---:|---:|---|
| `openspec/changes/` active | 9 | 0 | Keep active changes and statuses from `active-changes.yaml`; P0 hardening and the research-intelligence data-model foundation were completed and archived on 2026-07-13. |
| `openspec/changes/archive/` historical | 51 | 3 | Preserve historical task state; do not fabricate validation ledgers after archival. |

## Reconciliation decisions

- `openstock-four-phase-hardening` was the authoritative P0 prerequisite. Its
  226 tasks and 85 validation rows now pass the completion verifier and its
  accepted capability contract is synchronized under `openspec/specs/`.
- `research-intelligence-data-model-foundation` is completed and archived. Its
  40 tasks and five evidence rows pass the completion verifier; the accepted
  contract is synchronized under `openspec/specs/`, unblocking
  `symbol-knowledge-memory`.
- Other active changes remain `partial`, `planned`, or `in_progress` as listed
  in `openspec/active-changes.yaml`. They are not completion-ready and are not
  marked complete by this report.
- The active registry currently lists `tui-slash-command-on-typing-search` as
  `in_progress`, while the generated `openspec list --json` view has reported
  its implementation as complete. This is retained as an explicit registry
  reconciliation discrepancy; no status is changed without owner confirmation
  and its own completion evidence.
- Historical archived changes without `validation.md` retain their original
  execution history. Missing historical evidence is recorded as a governance
  gap, not backfilled with present-day commands.
- No task checkbox was changed solely because a change was archived, merged, or
  present in Git history.

Future archival must provide a validation ledger and pass
`scripts/check-openspec-completion.py` before the archive move. This report is
the reconciliation artifact for task 4.42; it does not make any incomplete
change complete.
