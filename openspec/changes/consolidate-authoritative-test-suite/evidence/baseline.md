# Issue #348 baseline evidence

Recorded on 2026-07-21 before test-consolidation, fixture, runner, routing or
workflow changes.

## Identity and command

| Field | Value |
| --- | --- |
| Commit | `e5472292b1a25067b8d689eab7a5b747cfd8d2dd` |
| Tracked working tree | clean (`git status --porcelain=v1` emitted no paths) |
| OS | Linux 6.8.0-71-generic, x86_64 |
| CPU | Intel Core i5-9600K, 6 logical CPUs / 6 cores |
| Memory at measurement | 31 GiB total, 22 GiB available |
| Python | CPython 3.13.5 |
| DuckDB | 1.5.4 |
| pytest | 9.1.1 |
| `vnalpha/uv.lock` SHA-256 | `40e81ae61a4ab14f4976f4b7fc2cb9f9cdb948d4e015885d13e0a483137f2113` |
| `vnalpha/pyproject.toml` SHA-256 | `bedbb32d1e31de2a0f10c6f39fb4ab8f1abde1a003b305f6384f76289a5f27bd` |
| Installed dependency-set SHA-256 | `e1cbc5a963fdcf432b7cc7f381617ee2a7c73d492bd21eaa5d91e505f58753c2` |

The project virtual environment created by `uv sync --extra dev` did not
include `pip`. The two package-resource tests correctly invoke
`sys.executable -m pip wheel`, so the unprepared local environment failed with
`No module named pip`. `uv pip install pip` made that exact child interpreter
provide `pip 26.1.2`; all three package-resource tests then passed. This is
local test-environment preparation, not a product or test-suite change.

Collection command:

```bash
cd vnalpha && uv run pytest --collect-only -q
```

Full sequential command:

```bash
cd vnalpha && /usr/bin/time -f 'full_wall_seconds=%e\nfull_user_seconds=%U\nfull_system_seconds=%S\nfull_max_rss_kb=%M' \
  uv run pytest --durations=100 --durations-min=0.20 \
  --junitxml=/tmp/issue348-baseline-pip.xml
```

## Result

| Measure | Result |
| --- | ---: |
| Collected tests | 3,303 |
| Test files | 275 |
| Collection wall time | 7.12 s |
| Collection max RSS | 200,552 KiB |
| Full result | 3,303 passed |
| pytest reported duration | 632.69 s |
| Measured wall duration | 634.17 s |
| User CPU time | 750.09 s |
| System CPU time | 42.07 s |
| Max RSS | 1,122,984 KiB |

The full JUnit report had 3,303 cases, 0 failures, 0 errors and 0 skips. The
top 100 durations at or above 0.20 s are retained in
[`baseline-top-100.txt`](baseline-top-100.txt).

## Runtime by file and initial domain

JUnit class names were resolved to the longest matching collected
`tests/**/test_*.py` path before aggregation. This prevents test classes and
parameterized cases from being counted as separate files.

| File | Tests | JUnit time |
| --- | ---: | ---: |
| `tests/test_command_handlers.py` | 31 | 71.68 s |
| `tests/test_issue_254_calendar_validity.py` | 15 | 45.76 s |
| `tests/test_evals_package_resources.py` | 3 | 23.74 s |
| `tests/test_executor_and_policy.py` | 29 | 23.58 s |
| `tests/test_outcome_evaluator.py` | 26 | 19.11 s |
| `tests/test_data_availability_integration.py` | 7 | 16.61 s |
| `tests/test_symbol_memory_maintenance.py` | 7 | 14.80 s |
| `tests/test_issue_167_golden_conversation.py` | 5 | 12.26 s |
| `tests/test_tui_terminal_integrity.py` | 19 | 12.21 s |
| `tests/commands/test_sandbox_commands.py` | 22 | 8.52 s |
| `tests/sandbox/test_repository_quality.py` | 30 | 8.40 s |
| `tests/test_r4_session.py` | 19 | 7.94 s |
| `tests/test_canonical_quarantine.py` | 27 | 7.80 s |
| `tests/test_ask_cli.py` | 42 | 7.36 s |
| `tests/commands/test_research_automation_commands.py` | 32 | 6.80 s |
| `tests/test_chat_local_commands.py` | 21 | 6.65 s |
| `tests/test_symbol_memory_commands.py` | 9 | 6.62 s |
| `tests/test_r0_gaps.py` | 16 | 6.55 s |
| `tests/test_tui_pilot.py` | 16 | 5.90 s |
| `tests/test_tui_workspace.py` | 18 | 5.90 s |

| Initial directory domain | Tests | JUnit time |
| --- | ---: | ---: |
| root `tests/` files | 2,837 | 569.50 s |
| `tests/sandbox/` | 315 | 36.39 s |
| `tests/commands/` | 80 | 19.97 s |
| `tests/workspace_context/` | 71 | 3.01 s |

The canonical manifest will replace these coarse directory domains with the
five contract owners specified by the change; the table is a baseline, not an
ownership decision.

## Aggregate duplication observed before the change

`make verify-hardening` invokes `verify-r0`, `verify-r2-ci`, the complete
`test-vnalpha`, `verify-r4`, then a second direct
`openstock-verify --ci`.

| Repeated unit | First aggregate invocation | Repeated by | Count in `verify-hardening` |
| --- | --- | --- | ---: |
| `test_phase5_e2e.py`, `test_features.py`, `test_warehouse.py`, `test_command_warehouse.py`, `test_r0_gaps.py` | `verify-r0` | complete `test-vnalpha` | 2 each |
| `test_r4_permissions.py`, `test_r4_session.py`, `test_r4_trace.py`, `test_r4_clear.py`, `test_r4_persistence.py`, `test_r4_controller_persistence.py` | complete `test-vnalpha` | `verify-r4` | 2 each |
| `packaging/scripts/openstock-verify --ci` | `verify-r2-ci` | direct final command | 2 |

The current `vnalpha` GitHub Actions job also runs the five R0 files through
`make verify-r0` before the full suite, so that job duplicates those files.
The fourteen targeted repository-regression node IDs are likewise collected by
the later full suite. No current workflow can deliberately skip the `vnalpha`
or `vnstock` jobs for a documentation/OpenSpec-only pull request: all three
jobs (`consistency`, `vnalpha`, `vnstock`) are unconditional.

## Migration and docs-lane baseline limits

There is no existing full-migration invocation counter or fixture timing hook,
so its baseline value is **not yet measurable**. Task 1.6 remains open until
the fixture work adds an explicit counter and records before/after values.
Likewise, no docs/OpenSpec-only pull request run on this commit exists from
which to report a truthful job wall time; the static workflow inspection above
records the pre-change behavior only. These unknowns are intentionally not
presented as passing measurements.
