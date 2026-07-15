# Validation: Required CI merge gates

## Status

```text
Workflow and aggregate gate: implemented
Repository consistency contract: implemented
Checker tests: pass
Branch-protection documentation: updated
Full repository CI and aggregate gate: pass
Live GitHub ruleset verification: pending administrator evidence in #147
```

## Required final commands

```bash
python scripts/check-repo-consistency.py
python -m pytest -q scripts/tests/test_check_repo_consistency.py scripts/tests/test_check_openspec_completion.py
make lint-vnalpha
make verify-r0
make test-vnalpha
python -m build --wheel --sdist --no-isolation --outdir /tmp/vnalpha-dist ./vnalpha
```

## Evidence

| UTC timestamp | Commit SHA | Phase/task | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-15T16:05:00Z | `local source export + working tree` | 1.1–2.3 | repository consistency checker | 0 | repository consistency passed | local command transcript |
| 2026-07-15T16:05:00Z | `local source export + working tree` | 2.1–2.3 | checker and OpenSpec checker tests | 0 | 15 tests passed | local command transcript |
| 2026-07-15T16:05:00Z | `local source export + working tree` | 2.1–2.3 | Ruff check and format | 0 | all checks passed | local command transcript |
| 2026-07-15T16:06:47Z | `1adcae5db3ab1b0fcb22139874b27508228418fc` | 1.1–3.1 | `openstock-ci` run #47 (`29431049414`) | 0 | repository consistency, checker tests, Ruff, focused regressions, R0, complete vnalpha suite, vnstock contracts, both package builds and Required merge gate passed | GitHub Actions run and diagnostics |

Final implementation SHA: `1adcae5db3ab1b0fcb22139874b27508228418fc`
Administrator ruleset evidence: `pending issue #147`
