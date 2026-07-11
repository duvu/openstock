# Validation: OpenStock four-phase hardening

## Status

```text
OpenSpec authored: yes
Runtime implementation: not started in this PR
Validation commands executed: no
Phase gates: pending
```

This file is the evidence ledger. Do not replace `pending` with `pass` without attaching exact command evidence for the tested commit.

## Baseline

| Field | Value |
|---|---|
| Baseline branch | `main` |
| Baseline commit | To be recorded by task 0.1 |
| OpenSpec branch | `agent/openstock-four-phase-hardening-openspec` |
| Runtime implementation PRs | Pending |
| Latest required-check result | Pending |

## Evidence row format

Every executed command must add one row:

| UTC timestamp | Commit SHA | Phase/task | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| Pending | Pending | Pending | Pending | — | Not executed | — |

Rules:

```text
- timestamp must be UTC
- commit SHA must be the code that was tested
- command must be exact and reproducible
- exit is numeric
- summary includes pass/fail counts or concise outcome
- artifact is CI run/job/log, local attached log, or committed report
```

## Phase 1 validation matrix

| Gate | Required evidence | Status |
|---|---|---|
| Denied tracked paths removed | `git ls-files` report | Pending |
| Unapproved gitlinks removed | `git ls-files --stage` report | Pending |
| Ignore rules verified | `git check-ignore -v` cases | Pending |
| Repository hygiene verifier | `make repo-hygiene` | Pending |
| Secret/sensitive scan | scanner command/report | Pending |
| Deterministic workspace root | focused tests from multiple CWDs | Pending |
| Workspace lock exclusivity | multi-process tests | Pending |
| Lost-update prevention | concurrent mutation tests | Pending |
| Lifecycle invariants | create/archive/resume/new/status tests | Pending |
| Legacy migration | migration and backup tests | Pending |
| Retention/compaction | before/after/archive tests | Pending |
| Redaction/export | E2E sensitive-text test | Pending |
| Phase 1 result | all above | **Pending** |

## Phase 2 validation matrix

| Gate | Required evidence | Status |
|---|---|---|
| Current prompt/context separation | message-construction tests | Pending |
| Historical context marked untrusted | prompt contract tests | Pending |
| Safety current-request only | malicious-context tests | Pending |
| Classification current-request only | intent isolation tests | Pending |
| `store_raw=false` | persistence tests | Pending |
| `store_raw=true` bounded behavior | persistence tests | Pending |
| Prepared turn built once | classifier/planner call-count tests | Pending |
| Exact plan execution | plan hash/identity tests | Pending |
| Auto execute single preparation | controller integration test | Pending |
| Approval executes stored plan | controller integration test | Pending |
| Busy request handling | headless TUI test | Pending |
| Workspace hook resilience | injected failure test | Pending |
| Corrupt workspace recovery | headless TUI recovery test | Pending |
| Phase 2 result | all above | **Pending** |

## Phase 3 validation matrix

| Gate | Required evidence | Status |
|---|---|---|
| Atomic data lock | multi-process test | Pending |
| Owner-safe release/stale replacement | focused tests | Pending |
| Strict explicit dates | zero-side-effect invalid-date test | Pending |
| Cache eligibility | score/feature/canonical/benchmark/quality/lineage matrix | Pending |
| Cache rejection observability | event test | Pending |
| Verified artifact refs | research-tool matrix | Pending |
| Missing sector behavior | shortlist payload test | Pending |
| Real compaction command path | command E2E | Pending |
| `/new` namespace | parser/chat/TUI tests | Pending |
| TODO transition events | resize/toggle tests | Pending |
| Session override isolation | two-session test | Pending |
| Grounded source refs | missing-ref fallback tests | Pending |
| Phase 3 result | all above | **Pending** |

## Phase 4 validation matrix

| Gate | Required evidence | Status |
|---|---|---|
| Ruff check/format | `make lint-vnalpha` | Pending |
| Root eval targets | Make target tests | Pending |
| Packaged corpus | wheel/sdist file inspection | Pending |
| Installed wheel eval | isolated install command | Pending |
| Debian/package eval | package test or approved defer | Pending |
| Fixture-contract eval | `make eval-research-answers` | Pending |
| Runtime-replay eval | `make eval-research-runtime` | Pending |
| Runtime replay covers all research intents | report | Pending |
| Negative runtime cases | report | Pending |
| Network prohibited | test | Pending |
| Repository hygiene in CI | workflow run | Pending |
| Secret scan in CI | workflow run | Pending |
| Full tests | `make test-vnalpha` | Pending |
| R4 | `make verify-r4` | Pending |
| Packaging verify | `packaging/scripts/openstock-verify --ci` | Pending |
| OpenSpec verifier | script command | Pending |
| Required checks/branch protection | documented settings/check run | Pending |
| Phase 4 result | all above | **Pending** |

## Final command matrix

Run from repository root on the final implementation SHA:

```bash
make repo-hygiene
make lint-vnalpha
make test-vnalpha
make verify-r4
packaging/scripts/openstock-verify --ci
make eval-research-answers
make eval-research-runtime
python scripts/check-openspec-completion.py \
  openspec/changes/openstock-four-phase-hardening
```

Additional installed-package validation:

```bash
python -m build vnalpha
python -m venv /tmp/openstock-hardening-wheel
/tmp/openstock-hardening-wheel/bin/pip install vnalpha/dist/*.whl
/tmp/openstock-hardening-wheel/bin/vnalpha eval research-answers --ci
/tmp/openstock-hardening-wheel/bin/vnalpha eval research-runtime --ci
```

Exact commands may be adjusted to the repository packaging interface, but equivalent installed-package proof is mandatory.

## Deferred work register

No tasks are deferred at OpenSpec creation time.

Required defer format:

```text
Task ID:
Reason:
Owner:
Dependency:
Risk accepted until:
Approval reference:
```

A deferred task does not count as complete. The final gate may pass with a defer only if the normative spec explicitly permits it and approval is recorded.

## Blockers

None recorded at OpenSpec creation time.

## Next executable task

```text
Task 0.1 — record baseline commit, denied tracked paths, gitlinks, open PRs, and CI state.
```

## Completion record

```text
Final implementation SHA: Pending
Final CI run: Pending
OpenSpec verifier result: Pending
Ready to archive: No
```