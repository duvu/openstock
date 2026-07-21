# Required CI and branch protection

> **Status:** repository policy and administrator verification checklist.
>
> The executable workflow is `.github/workflows/openstock-ci.yml`. This document
> must be updated in the same pull request whenever workflow names, job names or
> merge-gate behavior change.

## Stable required checks

`openstock-ci` runs on every pull request and every push to `main`; it has no
path filters that can make required checks disappear. Configure the `main`
branch ruleset to require all of these exact checks:

```text
openstock-ci / Repository consistency
openstock-ci / vnalpha lint and tests
openstock-ci / vnstock contracts and package
openstock-ci / Required merge gate
```

`Required merge gate` uses `if: always()` and accepts only `success` or an
intentional `skipped` conclusion from every routing consumer. The change-impact
classifier keeps the consistency lane on every pull request, skips runtime work
for docs/OpenSpec-only changes, and escalates unknown paths by failing routing.
A failed, cancelled or missing component gate must therefore prevent the
aggregate gate from succeeding.

## Required GitHub settings

For the `main` branch or default-branch ruleset, enable:

- Require a pull request before merging.
- Require status checks to pass before merging.
- Require branches to be up to date before merging.
- Select the four exact `openstock-ci` checks listed above.
- Do not allow bypassing the above settings.
- Block force pushes and branch deletion.

Repository administrators must verify these settings in GitHub after workflow
changes. Issue #147 owns the verification record; code and documentation alone
cannot assert that an external repository setting is active.

## Emergency bypass

Ordinary maintainer convenience is not an emergency. A bypass is acceptable only
for an active security or production incident when waiting for normal validation
creates greater harm.

Before bypass when operationally possible, create a P0 incident issue recording:

- incident owner and reason;
- exact PR and commit SHA;
- which required check is unavailable or failing;
- expected user/data impact;
- rollback plan.

After any bypass:

1. run the complete `openstock-ci` workflow against the merged SHA;
2. record exact run IDs and artifacts in the incident issue;
3. revert or repair immediately if any required gate fails;
4. create a focused prevention issue before closing the incident.

A bypassed merge is not considered validated until all four required checks pass
on the merged SHA.

## Verification record template

Record the following in issue #147 after an administrator inspects the active
ruleset:

```text
Verified at (UTC):
Verified by:
Protected branch/ruleset:
Require pull request: yes/no
Require branch up to date: yes/no
Bypass disabled: yes/no
Required checks:
  - openstock-ci / Repository consistency
  - openstock-ci / vnalpha lint and tests
  - openstock-ci / vnstock contracts and package
  - openstock-ci / Required merge gate
Evidence reference:
```

## OpenSpec lifecycle

Passing CI does not automatically complete OpenSpec tasks. Task checkboxes and
lifecycle changes require an exact-SHA evidence ledger and human review. Merge
protection ensures those records cannot be accepted from a branch whose required
runtime, package or repository checks are red.
