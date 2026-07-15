# Design: Required CI merge gates

## Decisions

### Required checks must always exist

`openstock-ci` has no pull-request path filters. All validation jobs are created
for every pull request, so branch protection does not wait indefinitely for a
check that was omitted by workflow filtering.

### Aggregate gate is always evaluated

`Required merge gate` depends on repository consistency, `vnalpha`, and
`vnstock`, and uses `if: always()`. It explicitly asserts that all three results
are `success`. Failed, cancelled or skipped dependencies therefore cannot make
the aggregate gate green.

The component checks remain visible and should also be required in the GitHub
ruleset for diagnostic clarity.

### Repository consistency checks workflow and documentation together

`check-repo-consistency.py` rejects:

- pull-request or `main` push path filters in `openstock-ci`;
- missing component/aggregate job names;
- an aggregate gate that does not assert all component results;
- branch-protection documentation missing current check names/settings;
- stale references to the deleted `vnalpha-ci` workflow.

Unit tests preserve those invariants.

### External settings cannot be asserted by code

GitHub branch protection/rulesets are outside the repository tree. The code PR
must not claim enforcement is active merely because a workflow and document
exist. Issue #147 remains open until an administrator records the live settings
using the documented evidence template.

### Emergency bypass is exceptional and auditable

A bypass requires an active security/production incident, exact SHA, owner,
rollback plan, and complete post-merge CI. Ordinary maintainer convenience is
not an emergency.

### Code and documentation move together

Any future workflow/job-name or merge-gate change must update the checker,
checker tests, branch-protection document, OpenSpec and required CI in the same
pull request.

## Non-goals

- No automatic modification of GitHub administrator settings from CI.
- No weakening of existing runtime, package or OpenSpec validation.
- No claim that a green aggregate gate alone configures branch protection.
