# Research Scenario Plan Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a persisted, research-only scenario plan for a symbol, exposed through a slash command, local tool, and assistant intent without producing trading-execution instructions.

**Architecture:** A `ScenarioPlanBuilder` will consume the existing deterministic deep-analysis artifact and level snapshots, create a linked `ResearchScenarioPlan`, validate every rendered string through a research-only policy gate, then persist the result. The existing command, local-tool, and assistant registries will expose that one builder without adding network, brokerage, account, allocation, or execution capabilities.

**Tech Stack:** Python 3.10+, DuckDB, pytest, existing `vnalpha` command/tool/assistant policy infrastructure.

---

## File structure

- Create: `src/vnalpha/research_intelligence/scenario_plan.py` — typed plan model, deterministic builder, scenario-tree construction, persistence call.
- Create: `src/vnalpha/research_intelligence/scenario_policy.py` — recursive text validator and required research-only disclaimer.
- Create: `src/vnalpha/research_intelligence/scenario_templates.py` — shared safe rendering labels/templates.
- Create: `src/vnalpha/tools/scenario.py` — `ToolOutput` adapter for the builder.
- Create: `src/vnalpha/commands/handlers/research_plan.py` — `/research-plan` renderer.
- Modify: `src/vnalpha/warehouse/schema.py`, `migrations.py`, `repositories.py` — durable scenario-plan table and repository helpers.
- Modify: `src/vnalpha/tools/setup.py`, `src/vnalpha/policy/tool_policy.py`, `src/vnalpha/policy/command_policy.py` — read-only capability and registration.
- Modify: `src/vnalpha/commands/setup.py` — slash-command metadata and handler registration.
- Modify: `src/vnalpha/assistant/intent.py`, `models.py`, `planner.py`, `synthesizer.py` — scenario intent, deterministic plan, and safe synthesis instruction.
- Modify: `tests/test_deep_analysis.py`, `tests/test_warehouse.py`, `tests/test_command_handlers.py`, `tests/test_tools.py`, `tests/test_intent_and_planner.py`, `tests/test_synthesizer_and_app.py` — behaviour-level coverage.

### Task 1: Define the policy contract before generating content

**Files:**
- Create: `src/vnalpha/research_intelligence/scenario_policy.py`
- Create: `tests/test_scenario_policy.py`

- [ ] **Step 1: Write failing validator tests.**

```python
def test_validator_accepts_research_only_plan_language() -> None:
    validate_research_only_language({"disclaimer": RESEARCH_ONLY_DISCLAIMER})


@pytest.mark.parametrize("text", ["Buy FPT now.", "Place an order.", "Allocate capital."])
def test_validator_rejects_execution_instruction(text: str) -> None:
    with pytest.raises(ScenarioLanguageValidationError):
        validate_research_only_language({"summary": text})
```

- [ ] **Step 2: Run the focused tests and confirm they fail because the module is absent.**

Run: `PYTHONPATH=src pytest tests/test_scenario_policy.py -q`

- [ ] **Step 3: Implement the minimal policy module.**

```python
RESEARCH_ONLY_DISCLAIMER = (
    "Research-only context; not an execution instruction; requires future confirmation."
)


class ScenarioLanguageValidationError(ValueError):
    pass


def validate_research_only_language(value: object) -> None:
    # Flatten strings recursively; reject action wording and require the disclaimer.
```

- [ ] **Step 4: Re-run the focused tests and confirm they pass.**

Run: `PYTHONPATH=src pytest tests/test_scenario_policy.py -q`

### Task 2: Persist a linked `ResearchScenarioPlan`

**Files:**
- Modify: `src/vnalpha/warehouse/schema.py`
- Modify: `src/vnalpha/warehouse/migrations.py`
- Modify: `src/vnalpha/warehouse/repositories.py`
- Modify: `tests/test_warehouse.py`

- [ ] **Step 1: Write a failing migration/repository test.**

```python
def test_scenario_plan_record_persists_references_and_correlation(conn) -> None:
    assert "research_scenario_plan" in table_names(conn)
    save_research_scenario_plan(conn, plan)
    assert get_research_scenario_plan(conn, "FPT", "2025-01-31")["correlation_id"] == "corr-1"
```

- [ ] **Step 2: Run the focused test and confirm the table/helper is absent.**

Run: `PYTHONPATH=src pytest tests/test_warehouse.py -q -k scenario_plan`

- [ ] **Step 3: Add a stable schema and helpers.**

```sql
CREATE TABLE IF NOT EXISTS research_scenario_plan (
    scenario_plan_id VARCHAR PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    date DATE NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL,
    plan_json VARCHAR NOT NULL,
    setup_analysis_date DATE,
    level_snapshot_date DATE,
    evidence_snapshot_json VARCHAR NOT NULL,
    correlation_id VARCHAR NOT NULL,
    UNIQUE(symbol, date)
)
```

Store the complete plan and snapshot references as JSON; on repeat generation for the same symbol/date, replace the record while preserving a new generated-at value and correlation ID.

- [ ] **Step 4: Re-run the focused test and confirm it passes.**

Run: `PYTHONPATH=src pytest tests/test_warehouse.py -q -k scenario_plan`

### Task 3: Build and validate the deterministic scenario artifact

**Files:**
- Create: `src/vnalpha/research_intelligence/scenario_templates.py`
- Create: `src/vnalpha/research_intelligence/scenario_plan.py`
- Modify: `tests/test_deep_analysis.py`

- [ ] **Step 1: Write failing builder tests for required fields, tree branches, and missing-level caveat.**

```python
plan = ScenarioPlanBuilder(conn).build("FPT", "2025-01-31", correlation_id="corr-1")
assert {"current_setup", "key_levels", "confirmation_conditions", "invalidation_conditions", "scenario_tree", "checklist", "confidence", "caveats", "research_only_language"} <= set(plan)
assert set(plan["scenario_tree"]) == {"base_case", "confirmation_case", "failed_confirmation_case", "low_quality_drift_case"}

missing_level_plan = ScenarioPlanBuilder(conn_without_ohlcv).build("FPT", "2025-01-31")
assert any("level" in caveat.lower() for caveat in missing_level_plan["caveats"])
```

- [ ] **Step 2: Run the focused builder tests and confirm they fail because `ScenarioPlanBuilder` is absent.**

Run: `PYTHONPATH=src pytest tests/test_deep_analysis.py -q -k scenario`

- [ ] **Step 3: Implement the builder.**

```python
class ResearchScenarioPlan(TypedDict):
    symbol: str
    as_of_date: str
    current_setup: dict[str, object]
    key_levels: list[dict[str, object]]
    confirmation_conditions: list[str]
    invalidation_conditions: list[str]
    scenario_tree: dict[str, ScenarioBranch]
    risk_reward_estimate: dict[str, object] | None
    checklist: list[str]
    confidence: float
    caveats: list[str]
    research_only_language: str
    artifact_references: dict[str, object]
    correlation_id: str
```

Use `DeepAnalysisBuilder` and `get_candidate_score`; derive all conditions from persisted trend, levels, setup quality, confidence, risk flags, and missing data. Generate all four required branches. Include an explicitly caveated level-grounded estimate only when observed support, resistance, and reference close are available. Call `validate_research_only_language(plan)` immediately before persistence/return.

- [ ] **Step 4: Re-run the focused builder tests and confirm they pass.**

Run: `PYTHONPATH=src pytest tests/test_deep_analysis.py -q -k scenario`

### Task 4: Expose only the safe command and local tool

**Files:**
- Create: `src/vnalpha/tools/scenario.py`
- Create: `src/vnalpha/commands/handlers/research_plan.py`
- Modify: `src/vnalpha/tools/setup.py`
- Modify: `src/vnalpha/policy/tool_policy.py`
- Modify: `src/vnalpha/policy/command_policy.py`
- Modify: `src/vnalpha/commands/setup.py`
- Modify: `tests/test_tools.py`
- Modify: `tests/test_command_handlers.py`

- [ ] **Step 1: Write failing integration tests.**

```python
assert "scenario.generate_research_plan" in build_local_tool_registry(conn).names()
result = registry.execute(parse("/research-plan FPT --date 2025-01-31"), conn=conn, tool_executor=executor)
assert [panel.title for panel in result.panels] == ["Current Setup", "Key Levels", "Conditions", "Scenario Tree", "Checklist", "Caveats"]
```

- [ ] **Step 2: Run the focused tests and confirm the command/tool are unregistered.**

Run: `PYTHONPATH=src pytest tests/test_tools.py tests/test_command_handlers.py -q -k 'scenario or research_plan'`

- [ ] **Step 3: Implement minimal registrations and renderer.**

```python
ToolCapability(
    "scenario.generate_research_plan",
    ToolPermission.READ_FEATURES,
    True, True, True,
)
```

The command contract is `/research-plan SYMBOL [--date YYYY-MM-DD] [--with-evidence] [--with-regime]`. The tool adapter invokes the builder and reports missing-data caveats as warnings. The handler renders policy-validated plan fields only, then validates the complete renderable payload again before returning a result.

- [ ] **Step 4: Re-run the focused integration tests and confirm they pass.**

Run: `PYTHONPATH=src pytest tests/test_tools.py tests/test_command_handlers.py -q -k 'scenario or research_plan'`

### Task 5: Add assistant intent and synthesis guardrails

**Files:**
- Modify: `src/vnalpha/assistant/intent.py`
- Modify: `src/vnalpha/assistant/models.py`
- Modify: `src/vnalpha/assistant/planner.py`
- Modify: `src/vnalpha/assistant/synthesizer.py`
- Modify: `tests/test_intent_and_planner.py`
- Modify: `tests/test_synthesizer_and_app.py`

- [ ] **Step 1: Write failing assistant tests.**

```python
plan = PlanBuilder().build(IntentResult("generate_research_scenario", 1.0, {"symbol": "FPT", "date": "2025-01-31"}))
assert [(step.tool_name, step.required_permission) for step in plan.steps] == [("scenario.generate_research_plan", "READ_FEATURES")]
assert "scenario plans" in SYNTHESIZER_SYSTEM_PROMPT.lower()
```

- [ ] **Step 2: Run the focused tests and confirm the intent is unsupported.**

Run: `PYTHONPATH=src pytest tests/test_intent_and_planner.py tests/test_synthesizer_and_app.py -q -k scenario`

- [ ] **Step 3: Implement the intent mapping and research-only synthesis template.**

Add `generate_research_scenario` to the classifier prompt and `SUPPORTED_INTENTS`; map it to a single `scenario.generate_research_plan` read-feature step. Require synthesis to present current setup, observed conditions, branches, caveats, missing data, the research-only disclaimer, and future-confirmation language without changing them into an execution recommendation.

- [ ] **Step 4: Re-run the focused assistant tests and confirm they pass.**

Run: `PYTHONPATH=src pytest tests/test_intent_and_planner.py tests/test_synthesizer_and_app.py -q -k scenario`

### Task 6: Regression validation and OpenSpec evidence

**Files:**
- Modify: `openspec/changes/research-scenario-plan-engine/tasks.md`

- [ ] **Step 1: Run focused scenario tests.**

Run: `PYTHONPATH=src pytest tests/test_scenario_policy.py tests/test_deep_analysis.py tests/test_warehouse.py tests/test_tools.py tests/test_command_handlers.py tests/test_intent_and_planner.py tests/test_synthesizer_and_app.py -q`

- [ ] **Step 2: Run code quality checks.**

Run: `ruff check src tests && ruff format --check src tests`

- [ ] **Step 3: Run the full vnalpha test suite.**

Run: `PYTHONPATH=src pytest -q`

- [ ] **Step 4: Mark each completed OpenSpec task immediately after its evidence passes.**

Replace only the matching `- [ ]` item in `openspec/changes/research-scenario-plan-engine/tasks.md` with `- [x]`; do not alter unrelated user changes.
