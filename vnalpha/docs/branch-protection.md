# Hardening branch protection

The hardening workflow is `.github/workflows/vnalpha-ci.yml`. Repository
settings should require its `validate` job (`vnalpha-ci / validate`) before a
pull request can merge when a change touches `vnalpha`, `openspec`,
`packaging`, `Makefile`, or the workflow itself.

Required policy:

- changes merge through a pull request;
- the `vnalpha-ci / validate` check is required, must be successful, and must
  be present for every applicable pull request;
- branches must be up to date with the protected base branch before merge;
- force-push and direct-merge permissions remain limited to repository
  maintainers;
- a missing, cancelled, or failing required check blocks merge;
- the workflow may cancel obsolete pull-request runs, but it must not cancel
  validation on `main`.

The workflow itself is the source of the gate order: repository hygiene and
secret scanning, dependency installation, focused tests, Ruff, the full suite,
R4, deployment verification, fixture evaluation, runtime replay, installed
wheel/sdist evaluation, and OpenSpec completion verification. A merge or PR
state change never checks OpenSpec tasks automatically; task checkboxes require
the evidence ledger and human review.
