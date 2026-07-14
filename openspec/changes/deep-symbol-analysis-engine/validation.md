# Validation evidence

## Issue #92 readiness-contract follow-up — 2026-07-14

| Check | Outcome | Evidence |
|---|---|---|
| Focused readiness and dependent tests | Passed | `uv run pytest -q tests/test_deep_analysis_readiness.py tests/test_phase3_cache_eligibility.py tests/test_data_availability_service_split.py tests/test_data_availability_ensure.py tests/test_data_availability_integration.py tests/test_data_availability_checks.py tests/test_data_availability_lock_and_observability.py` exited `0`; later focused regression checks also exited `0`. |
| `make test-vnalpha` | Passed | Exit code `0`; full `vnalpha` suite completed at 100% after #92 evidence, freshness, missing-symbol, lock, and audit-sanitization fixes. |
| `make verify-r4` | Passed | R4 acceptance suite completed at 100%. |
| `packaging/scripts/openstock-verify --ci` | Passed with existing systemd warning | `16 OK`, `1 WARN`, `0 FAIL`, final status `PASS`; warning is for `openstock-daily-pipeline.service`. |
| `openspec validate deep-symbol-analysis-engine --strict` | Passed | Change reported valid. |
| `make lint-vnalpha` | Not green | The only formatting failure is pre-existing tracked `vnalpha/src/vnalpha/symbol_memory/safe_files.py`; #92 files pass targeted Ruff/format checks. |
| Module static checks | Passed | Targeted Ruff, format, byte-compilation, and the Python no-excuse checker pass for modified readiness modules. |
| Manual CLI QA | Passed | Help succeeds for `sync symbols`, `sync ohlcv`, `sync index`, `build canonical`, `build features`, and `score`; invalid `vnalpha build canonical --symbol` exits `2` before execution. `vnalpha data --help` is intentionally deferred to #77. |
| Runtime readiness audit | Passed | Three runtime hypotheses were exercised: exception leakage is sanitized into a five-artifact failed result; audit correlation exists before ensure; arbitrary warning text does not control typed artifact attribution. A provider-secret audit regression now records only a generic summary and error type. |

Residual risk: repository-wide formatting remains blocked by the pre-existing
`symbol_memory/safe_files.py` formatting drift. This issue does not modify that
file, and no green repository lint gate is claimed.
