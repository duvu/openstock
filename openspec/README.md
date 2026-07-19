# OpenSpec governance

`openspec/changes/` contains changes with unresolved product or implementation scope. Completed, superseded, duplicate, abandoned or incompatible changes belong under `openspec/changes/archive/`.

The product roadmap is GitHub issue [#238 — OpenStock core data and knowledge loop](https://github.com/duvu/openstock/issues/238). The local [`active-changes.yaml`](active-changes.yaml) registry tracks only OpenSpec lifecycle and evidence; it does not own priority or execution order.

## Responsibility split

| Artifact | Owns | Must not own |
|---|---|---|
| GitHub issue | priority, dependencies, delivery status, scope, acceptance criteria, closure | detailed design duplicated across files |
| Master issue #238 | dependency order and track-level progress | implementation detail |
| OpenSpec change | requirements, design, tasks and validation evidence | a competing P0/P1 queue |
| Pull request | implementation diff and exact verification results | roadmap reprioritization hidden in PR prose |
| Stable docs | architecture, concepts and operating guidance | live status checklists |

## Scheduling rules

1. Every scheduled OpenSpec change must link one or more GitHub issues in `active-changes.yaml`.
2. An OpenSpec without an open linked issue is `proposed_untracked` or `review_required`; it cannot set current priority.
3. GitHub issue dependencies are authoritative. Do not mirror `blocked_by` graphs in the OpenSpec registry.
4. Closing an issue requires acceptance evidence. Reconcile the linked OpenSpec at the same time:
   - archive it if the accepted scope is complete;
   - otherwise create a focused follow-up issue for the remaining scope.
5. Search active changes, archived changes, accepted specs and GitHub Issues before creating overlapping work.
6. Check a task only when the requested code and evidence exist; PR prose alone is not evidence.
7. Sync only accepted implemented requirements into `openspec/specs/`.
8. Change priority or delivery order in GitHub Issues and update #238, never in this README.

## Registry fields

Each entry in `active-changes.yaml` records:

- `status`: lifecycle state of the specification/implementation;
- `github_issues`: linked issue numbers;
- `roadmap_state`: `scheduled`, `proposed_untracked` or `review_required`;
- `summary`: stable scope summary;
- `evidence`: current, honest implementation/validation state.

The registry deliberately contains no `priority`, `p0_change` or dependency queue.

## Research boundary

All changes preserve the read-only research boundary: no broker, order placement, account management, portfolio mutation, allocation, margin, transfer or trading execution.

The assistant must not gain unrestricted SQL, filesystem, shell or code execution and must not autonomously call `data.fetch`. Stored documents, memory, news and model output remain untrusted evidence.
