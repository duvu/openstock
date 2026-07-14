# Validation Evidence: Research Scenario Plan Engine

## Automated validation

- `make lint-vnalpha` — passed: Ruff reported all checks passed and 585 files already formatted.
- `make test-vnalpha` — passed: full `pytest -q` suite completed with exit code 0.
- Focused regression command:

  ```text
  cd vnalpha && pytest -q tests/test_research_scenario_plan_engine.py \
    tests/test_safety_boundary.py tests/test_command_handlers.py
  ```

  Result: passed.

- `openspec validate research-scenario-plan-engine --type change --strict` — passed.

## Manual CLI validation

An isolated DuckDB warehouse was seeded with persisted FPT candidate-score and
daily-bar artifacts. The packaged CLI, invoked without its environment-wrapper
warehouse override, produced all four scenario branches, persisted the scenario,
level, and evidence records, and rendered setup, confidence, and the caveated
rough estimate.

- Help: `vnalpha cmd --help` — exit 0.
- Happy path: `vnalpha cmd '/research-plan FPT --date 2026-07-10'` — exit 0.
- Invalid input: `vnalpha cmd '/research-plan'` — exit 1 with
  `/research-plan requires exactly one symbol.`

## Policy audit

- Safe research-only conditional wording is accepted.
- Unsafe wording including `buy` and `purchase shares now` is rejected before
  scenario persistence or rendering.
