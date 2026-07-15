# Validation: Production market context v2

## Status

```text
Implementation: complete on pull request #145
Focused policy tests: pass
Related readiness/provisioning/repository tests: pass
Ruff changed-file checks: pass
Full CI and exact final SHA: pending pull request validation
```

## Required final commands

```bash
python scripts/check-repo-consistency.py
make lint-vnalpha
cd vnalpha && pytest -q tests/test_market_regime_builder.py tests/test_sector_strength_builder.py tests/test_sector_strength_regressions.py tests/test_market_context_production_policy.py
cd vnalpha && pytest -q tests/test_context_readiness.py tests/test_deep_analysis_readiness.py tests/test_issue_95_functional_blockers.py tests/test_data_provisioning_runtime_hardening.py tests/test_research_context_tools.py tests/test_research_context_commands.py tests/test_market_regime_repository.py
make verify-r0
make test-vnalpha
python -m build --wheel --sdist --no-isolation --outdir /tmp/vnalpha-dist ./vnalpha
```

## Evidence

| UTC timestamp | Commit SHA | Phase/task | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-15T13:40:00Z | `local source export + working tree` | 1.1-4.4 | focused market/sector production and legacy suites | 0 | 40 tests passed | local command transcript |
| 2026-07-15T13:44:00Z | `local source export + working tree` | 4.1 | related readiness, provisioning, command and repository suites | 0 | 103 tests passed | local command transcript |
| 2026-07-15T13:49:00Z | `local source export + working tree` | 1.1-4.4 | Ruff check and format on changed files | 0 | all checks passed | local command transcript |

Final implementation SHA: `pending`
