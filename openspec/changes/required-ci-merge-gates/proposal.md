## Why

PR #146 merged into `main` while `openstock-ci` was red. The workflow also used
path filters, so required check names could disappear entirely for some pull
requests. Branch-protection documentation still named a deleted workflow and an
obsolete check.

Issue #147 restores a stable, truthful merge-gate contract. Repository code can
make checks always present and aggregate their results, but GitHub branch/ruleset
settings remain an external administrator-controlled enforcement layer.

## What Changes

- Run `openstock-ci` on every pull request and every push to `main` without path
  filters.
- Add `openstock-ci / Required merge gate`, which always runs and succeeds only
  when repository consistency, `vnalpha`, and `vnstock` jobs all succeed.
- Add executable consistency checks that reject hidden/path-filtered required
  gates and stale branch-protection documentation.
- Update branch-protection documentation to exact workflow/job names, required
  GitHub settings, emergency bypass policy and an administrator evidence
  template.
- Add checker tests to required CI.
- Keep administrator verification as an explicit incomplete task until the live
  GitHub ruleset is inspected and recorded in issue #147.

## Capabilities

### Modified Capabilities

- `repository-delivery-governance`: stable CI check visibility, aggregate merge
  status, code/document consistency and external ruleset verification.

## Impact

- CI runs on documentation-only and root-only pull requests as well as source
  changes.
- A skipped, cancelled or failed component job makes the aggregate gate fail.
- This change does not claim that branch protection is active until an
  administrator records live ruleset evidence.
