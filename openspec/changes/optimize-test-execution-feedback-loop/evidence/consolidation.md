# Low-value test consolidation evidence

Commit pending at the time of this record. The baseline collection was 3,303
tests; the post-consolidation collection is 3,298 tests.

| Removed test | Disposition | Retained replacement evidence |
| --- | --- | --- |
| `test_p0_operations_truthfulness.py::test_calendar_resolution_fails_closed_outside_version` | Exact AST duplicate. | `test_ohlcv_gaps.py::test_implicit_session_resolution_fails_closed_outside_versioned_coverage` executes the same `latest_session_on_or_before(2027-01-04)` fail-closed assertion. |
| `test_outcome_evaluator.py::TestEvaluatorComplete::test_next_session_entry_bases_forward_return_for_benchmark` | Exact AST duplicate. | `TestEvaluatorComplete::test_next_session_entry_bases_forward_return` inserts the same FPT/VNINDEX bars and asserts the same entry, exit, forward-return and benchmark-return values. |
| `test_outcome_schema.py::TestOutcomeModels::test_default_horizons` | Exact AST duplicate. | `test_outcome_metrics.py::TestDefaultHorizons::test_default_horizons` asserts the same exported horizon list. |
| `test_tui.py::test_score_table_widget_exists` | Empty body (`pass`), no behavior observed. | No replacement is required because the test never imported or asserted a widget. Real Textual behavior remains covered by the non-empty TUI tests in the same module. |
| `test_tui.py::test_risk_panel_widget_exists` | Empty body (`pass`), no behavior observed. | No replacement is required because the test never imported or asserted a widget. Real Textual behavior remains covered by the non-empty TUI tests in the same module. |

Focused retained coverage passed, the affected files passed Ruff, and a complete
AST-body scan found no remaining exact duplicate test functions. The scan is not
used to classify financial, migration, package, recovery or security cases as
deletable; those boundaries remain retained unless a contract-level replacement
is separately demonstrated.
