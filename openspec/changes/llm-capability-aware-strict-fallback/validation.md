# Validation: Capability-aware strict-schema fallback

## Status

```text
Implementation: complete
Focused routing/structured-output tests: pass
Ruff: pass
R0: pass
Complete vnalpha suite: pass
vnstock provider/canonical contracts: pass
Both package builds: pass
Lifecycle: ready for review; archive after merge
```

## Required final commands

```bash
python scripts/check-repo-consistency.py
make lint-vnalpha
cd vnalpha && pytest -q tests/test_llm_capability_fallback.py tests/test_llm_structured_output.py tests/test_model_routing.py
make verify-r0
make test-vnalpha
python -m build --wheel --sdist --no-isolation --outdir /tmp/vnalpha-dist ./vnalpha
```

## Evidence

| UTC timestamp | Commit SHA | Phase/task | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-15T15:25:00Z | `local source export + working tree` | 1.1–4.1 | focused capability, structured-output and model-routing tests | 0 | 28 tests passed | local command transcript |
| 2026-07-15T15:25:00Z | `local source export + working tree` | 1.1–4.1 | Ruff check/format on changed Python files | 0 | all checks passed | local command transcript |
| 2026-07-15T15:47:07Z | `1a82ed837782b32950e50da80dad2ca599934959` | 1.1–4.2 | `openstock-ci` run #42 (`29429616769`) | 0 | repository consistency, hygiene, secret scan, Compose, OpenSpec checker tests, Ruff, focused #144 regressions, R0, complete vnalpha suite, vnstock contracts and both package builds passed | GitHub Actions run and uploaded diagnostics |

Final implementation SHA: `1a82ed837782b32950e50da80dad2ca599934959`
