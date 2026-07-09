# Design: Research Scenario Plan Engine

## Architecture

```text
/analyze SYMBOL or /research-plan SYMBOL
  -> ensure_symbol_analysis_ready
  -> DeepSymbolAnalysis
  -> level map
  -> setup evidence
  -> ScenarioPlanBuilder
  -> PolicyLanguageValidator
  -> ResearchScenarioPlan repository
  -> command/assistant/TUI rendering
```

## Proposed modules

```text
vnalpha/research_intelligence/scenario_plan.py
vnalpha/research_intelligence/scenario_policy.py
vnalpha/research_intelligence/scenario_templates.py
vnalpha/commands/handlers/research_plan.py
```

## Scenario tree

MVP scenario tree should include:

```text
base_case
confirmation_case
failed_confirmation_case
low_quality_drift_case
```

Each branch should include:

```text
condition
evidence to watch
risk context
caveat
```

## Risk/reward estimate

If included, this must be rough, level-grounded, and caveated.

Allowed wording:

```text
rough research estimate
level-based context
not an execution instruction
requires future confirmation
```

Disallowed wording:

```text
buy here
sell here
enter position
place stop
allocate capital
```

## Command contract

```text
/research-plan SYMBOL [--date YYYY-MM-DD] [--with-evidence] [--with-regime]
```

## Assistant integration

Intent:

```text
generate_research_scenario
```

Tool:

```text
scenario.generate_research_plan
```

## Validation

The final plan must pass policy wording validation before rendering or assistant synthesis.
