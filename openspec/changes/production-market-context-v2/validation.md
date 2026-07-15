# Validation: Production market context v2

## Status

```text
Implementation: complete on pull request #145
Focused policy tests: pass
Related readiness/provisioning/repository tests: pass
Repository consistency, Ruff, R0, full vnalpha suite and package build: pass
Final implementation SHA: 661f35ce1aebe7bc8e56b6f7490686cd2cfaa9a2
```

## Required final commands

```bash
python scripts/check-repo-consistency.py
make lint-vnalpha
make verify-r0
make test-vnalpha
python -m build --wheel --sdist --no-isolation --outdir /tmp/vnalpha-dist ./vnalpha
```

## Evidence

| UTC timestamp | Commit SHA | Phase/task | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-15T13:40:00Z | `local source export + working tree` | 1.1–1.3, 2.1–2.4, 3.1–3.4, 4.1–4.4 | focused market/sector production and legacy suites | 0 | 40 focused tests passed before branch publication | local command transcript |
| 2026-07-15T13:44:00Z | `local source export + working tree` | 4.1 | related readiness, provisioning, command and repository suites | 0 | 103 related tests passed before branch publication | local command transcript |
| 2026-07-15T14:14:20Z | `661f35ce1aebe7bc8e56b6f7490686cd2cfaa9a2` | 1.1–1.3, 2.1–2.4, 3.1–3.4, 4.1–4.4 | `make test-vnalpha` | 0 | Complete vnalpha suite passed, including production and explicit-v1 market-context fixtures | GitHub Actions `openstock-ci` run #35 (`29422339362`) |
| 2026-07-15T14:14:20Z | `661f35ce1aebe7bc8e56b6f7490686cd2cfaa9a2` | 4.5 | `python scripts/check-repo-consistency.py` | 0 | Repository, documentation and active OpenSpec contracts passed | GitHub Actions `openstock-ci` run #35 (`29422339362`) |
| 2026-07-15T14:14:20Z | `661f35ce1aebe7bc8e56b6f7490686cd2cfaa9a2` | 4.5 | `make lint-vnalpha` | 0 | Ruff lint and format checks passed | GitHub Actions `openstock-ci` run #35 (`29422339362`) |
| 2026-07-15T14:14:20Z | `661f35ce1aebe7bc8e56b6f7490686cd2cfaa9a2` | 4.5 | `make verify-r0` | 0 | Offline R0 pipeline passed | GitHub Actions `openstock-ci` run #35 (`29422339362`) |
| 2026-07-15T14:14:20Z | `661f35ce1aebe7bc8e56b6f7490686cd2cfaa9a2` | 4.5 | `make test-vnalpha` | 0 | Complete vnalpha test suite passed | GitHub Actions artifact `vnalpha-full-suite-log` from run #35 |
| 2026-07-15T14:14:20Z | `661f35ce1aebe7bc8e56b6f7490686cd2cfaa9a2` | 4.5 | `python -m build --wheel --sdist --no-isolation --outdir /tmp/vnalpha-dist ./vnalpha` | 0 | vnalpha wheel and sdist built successfully | GitHub Actions `openstock-ci` run #35 (`29422339362`) |

Final implementation SHA: `661f35ce1aebe7bc8e56b6f7490686cd2cfaa9a2`
