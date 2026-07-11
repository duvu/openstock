# Validation: Assistant Research Intelligence Tools

## Implementation evidence

The follow-up implementation adds or completes:

```text
vnalpha/src/vnalpha/assistant/app.py
vnalpha/src/vnalpha/assistant/groundedness.py
vnalpha/src/vnalpha/assistant/research_audit.py
vnalpha/src/vnalpha/assistant/synthesizer.py
vnalpha/src/vnalpha/warehouse/research_answer_schema.py
vnalpha/src/vnalpha/warehouse/migrations.py
vnalpha/docs/assistant-research-intelligence-tools.md
```

Focused test files:

```text
vnalpha/tests/test_assistant_research_intelligence_completion.py
vnalpha/tests/test_research_answer_audit_completion.py
vnalpha/tests/test_research_intent_classification_matrix.py
vnalpha/tests/test_research_policy_rewrite_completion.py
vnalpha/tests/test_research_tool_execution_completion.py
```

## Acceptance evidence represented by tests

| Requirement | Test evidence |
|---|---|
| Every research intent is classified | `test_research_intent_classification_matrix.py` |
| Every research intent has a deterministic plan | `test_every_research_intent_has_deterministic_plan` |
| Central policy permits bounded research tools and rejects `data.fetch` | `test_research_tools_use_central_safe_tool_policy`, `test_unsafe_execution_tool_remains_denied` |
| Registry contains research tools | `test_local_registry_exposes_all_bounded_research_tools` |
| Executor produces structured traced output | `test_executor_runs_market_context_plan_with_structured_missing_payload` |
| Template and source references reach synthesis | `test_research_prompt_contains_template_and_bounded_source_refs` |
| Valid grounded answer passes | `test_grounded_research_answer_passes_and_records_validation_metadata` |
| Unsupported claims are rewritten | `test_unsupported_claims_are_rewritten_with_deterministic_fallback` |
| Shortlist disclaimer is enforced | `test_shortlist_without_research_disclaimer_is_rewritten` |
| Scenario execution wording is removed | `test_execution_oriented_scenario_answer_is_rewritten_fail_closed` |
| Missing planned tool output fails before model call | `test_missing_required_tool_output_fails_before_model_call` |
| Audit table migration exists | `test_migrations_create_research_answer_audit_table` |
| AssistantApp persists audit metadata | `test_assistant_app_persists_validated_research_answer_audit` |

## Commands required

Run from repository root:

```bash
cd vnalpha
pytest -q \
  tests/test_assistant_research_intelligence_completion.py \
  tests/test_research_answer_audit_completion.py \
  tests/test_research_intent_classification_matrix.py \
  tests/test_research_policy_rewrite_completion.py \
  tests/test_research_tool_execution_completion.py
cd ..

make test-vnalpha
make lint-vnalpha
make verify-r4
packaging/scripts/openstock-verify --ci
```

## Current execution status

The implementation was authored through the GitHub connector, which does not provide a checked-out execution environment. The uploaded `ari-tests.png` contains only `NO LOG` and provides no test result evidence.

Therefore, no command is falsely reported as executed here. The PR must remain draft until the focused suite and repository gates above complete successfully in CI or a checked-out environment.

## Merge criteria

```text
focused tests pass
full vnalpha tests pass
Ruff check and format-check pass
R4 acceptance tests pass
openstock verification passes
no unresolved review or CI failures remain
```
