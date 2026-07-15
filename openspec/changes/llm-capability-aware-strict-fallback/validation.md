# Validation: Capability-aware strict-schema fallback

## Status

```text
Implementation: complete in working tree
Focused routing/structured-output tests: pass
Ruff changed-file checks: pass
Repository CI and exact final SHA: pending pull request
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

Final implementation SHA: `pending`
