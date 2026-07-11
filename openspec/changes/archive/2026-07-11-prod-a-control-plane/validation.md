# Validation evidence

All commands were run from the OpenStock worktree
`/tmp/openstock-prod-a-control-plane` with isolated warehouse and log paths.

## Passing checks

```text
VNALPHA_WAREHOUSE_PATH=/tmp/prod-a-control-plane-tui.duckdb \
VNALPHA_LOG_ROOT=/tmp/prod-a-control-plane-tui-logs \
pytest -q vnalpha/tests/test_tui_*.py
```

Result: all TUI tests passed.

```text
VNALPHA_WAREHOUSE_PATH=/tmp/prod-a-control-plane-r4.duckdb \
VNALPHA_LOG_ROOT=/tmp/prod-a-control-plane-r4-logs make verify-r4
```

Result: all R4 acceptance tests passed.

```text
VNALPHA_WAREHOUSE_PATH=/tmp/prod-a-control-plane-verify.duckdb \
VNALPHA_LOG_ROOT=/tmp/prod-a-control-plane-verify-logs \
packaging/scripts/openstock-verify --ci
```

Result: 16 OK, 1 existing systemd warning, 0 failures.

## Known baseline blocker

`make test-vnalpha` cannot complete collection on the current branch because
`vnalpha/tests/test_intent_and_planner.py` imports the missing pre-existing
`CONTEXT_INTENT_EXAMPLES` symbol from `vnalpha.assistant.intent`. This is
outside the control-plane files and is recorded rather than hidden.

The full `make lint-vnalpha` target also reports five pre-existing Ruff issues
in assistant/model-routing tests; the control-plane files pass targeted Ruff
checks.
