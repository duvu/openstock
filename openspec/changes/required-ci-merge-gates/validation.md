# Validation: Required CI merge gates

## Status

```text
Workflow and aggregate gate: implemented
Repository consistency contract: implemented
Checker tests: pass locally
Branch-protection documentation: updated
Full repository CI: pending pull request
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

## Local evidence

| UTC timestamp | Commit SHA | Phase/task | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-15T16:05:00Z | `local source export + working tree` | 1.1–2.3 | repository consistency checker | 0 | repository consistency passed | local command transcript |
| 2026-07-15T16:05:00Z | `local source export + working tree` | 2.1–2.3 | checker and OpenSpec checker tests | 0 | 15 tests passed | local command transcript |
| 2026-07-15T16:05:00Z | `local source export + working tree` | 2.1–2.3 | Ruff check and format | 0 | all checks passed | local command transcript |

Final implementation SHA: `pending`
Administrator ruleset evidence: `pending issue #147`
