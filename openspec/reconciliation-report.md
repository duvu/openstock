# OpenSpec task/evidence reconciliation

Recorded 2026-07-12 against the shared working tree.

## Inventory

| Location | Changes | With validation ledger | Decision |
|---|---:|---:|---|
| `openspec/changes/` active | 11 | 1 | Keep active changes and statuses from `active-changes.yaml`; only the P0 hardening change is being validated in this worktree. |
| `openspec/changes/archive/` historical | 51 | 3 | Preserve historical task state; do not fabricate validation ledgers after archival. |

## Reconciliation decisions

- `openstock-four-phase-hardening` is the authoritative P0 prerequisite. Its
  task and validation ledgers are being reconciled together; the completion
  verifier currently reports it incomplete because real tasks and final gates
  remain open.
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
