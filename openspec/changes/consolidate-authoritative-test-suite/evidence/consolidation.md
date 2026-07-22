# Low-value test consolidation evidence

The baseline collection was 3,303 tests. The first duplicate-removal pass
collected 3,298 tests; the later three schema-owner removals are recorded below
and require the final bounded collection evidence before a final count is
claimed.

| Removed test | Disposition | Retained replacement evidence |
| --- | --- | --- |
| `test_p0_operations_truthfulness.py::test_calendar_resolution_fails_closed_outside_version` | Exact AST duplicate. | `test_ohlcv_gaps.py::test_implicit_session_resolution_fails_closed_outside_versioned_coverage` executes the same `latest_session_on_or_before(2027-01-04)` fail-closed assertion. |
| `test_outcome_evaluator.py::TestEvaluatorComplete::test_next_session_entry_bases_forward_return_for_benchmark` | Exact AST duplicate. | `TestEvaluatorComplete::test_next_session_entry_bases_forward_return` inserts the same FPT/VNINDEX bars and asserts the same entry, exit, forward-return and benchmark-return values. |
| `test_outcome_schema.py::TestOutcomeModels::test_default_horizons` | Exact AST duplicate. | `test_outcome_metrics.py::TestDefaultHorizons::test_default_horizons` asserts the same exported horizon list. |
| `test_tui.py::test_score_table_widget_exists` | Empty body (`pass`), no behavior observed. | No replacement is required because the test never imported or asserted a widget. Real Textual behavior remains covered by the non-empty TUI tests in the same module. |
| `test_tui.py::test_risk_panel_widget_exists` | Empty body (`pass`), no behavior observed. | No replacement is required because the test never imported or asserted a widget. Real Textual behavior remains covered by the non-empty TUI tests in the same module. |
| `test_outcome_schema.py::TestMigrations::test_total_table_count` | Duplicate schema implementation count. | `test_warehouse.py::test_all_tables_created` is the canonical exact schema manifest; it asserts the complete owned table set. |
| `test_outcome_schema.py::TestMigrations::test_migrations_idempotent` | Duplicate migration idempotency/count contract. | `test_warehouse.py::test_run_migrations_idempotent` reruns migrations and asserts the canonical schema count. |
| `test_assistant_persistence.py::test_migrations_idempotent` | Duplicate migration idempotency/count contract. | `test_warehouse.py::test_run_migrations_idempotent` reruns migrations and asserts the canonical schema count. |

The retained migration owner passed through `make test-loop` in 1.4 seconds,
the affected files passed Ruff, and a complete AST-body scan found no remaining
exact duplicate test functions. The scan is not
used to classify financial, migration, package, recovery or security cases as
deletable; those boundaries remain retained unless a contract-level replacement
is separately demonstrated.

## Current-main reconciliation

The source-aware validator found five unrecorded #370 contract nodes and one
moved intent node. The intent entry was retargeted without adding coverage.
The five #370 nodes are distinct public or risk contracts and remain separate:
bounded canonical promotion, ready-evidence reuse, queue joining/escalation,
canonical-tail promotion and raw-evidence-tail sync.
To preserve the budget without weakening those contracts, three duplicate
Textual app-mount smoke tests were removed; the retained workspace-context
startup contract mounts the same application path and verifies the stronger
workspace lifecycle result.

The resulting source-aware inventory is 220 nodes with no unclassified test
definitions.
