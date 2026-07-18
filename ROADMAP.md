# OpenStock roadmap

The canonical product roadmap is GitHub issue [#209](https://github.com/duvu/openstock/issues/209).

GitHub Issues are the only source of truth for:

- current priority;
- delivery order and dependencies;
- implementation scope and acceptance criteria;
- status, ownership and closure evidence.

Repository documents describe stable architecture, product principles and operating procedures. They must not duplicate a live issue queue or publish a competing “current priority” list.

## Stable product direction

OpenStock develops in four evidence-driven layers:

1. trustworthy, provider-independent market data;
2. point-in-time research evidence and reproducible backtesting;
3. publication-aware fundamentals, official documents and verified events;
4. optional providers and intelligence features that conform to the same contracts.

The exact order within and across these layers is maintained in [#209](https://github.com/duvu/openstock/issues/209), not in this file.

## Work-item contract

Every scheduled change must have one primary GitHub issue containing:

- objective and user value;
- explicit `Depends on` and `Blocks` relationships when applicable;
- scope and non-goals;
- testable acceptance criteria;
- validation and rollout evidence required for closure.

A focused pull request should normally close one primary issue with `Closes #N`.

## OpenSpec relationship

OpenSpec supports an issue with requirements, design decisions, tasks and validation evidence. It does not assign roadmap priority.

- Every scheduled OpenSpec change links at least one GitHub issue.
- An unlinked OpenSpec is proposed/untracked and cannot enter the execution queue.
- When an issue closes, its OpenSpec is reconciled and archived or a follow-up issue is created for any remaining scope.
- Priority and dependency changes are made in GitHub Issues and reflected in #209.

When roadmap ownership migrates to a successor issue, first move this pointer and close/merge #209 only after the successor issue and evidence handoff are recorded.

## Research boundary

The roadmap is limited to read-only research. Broker, account, order, portfolio mutation, allocation, margin, transfer and trading-execution capabilities remain out of scope.
