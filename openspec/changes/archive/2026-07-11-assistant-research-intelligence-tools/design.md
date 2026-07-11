# Design: Assistant Research Intelligence Tools

## Architecture

```text
ChatController / CLI ask
  -> IntentClassifier
  -> PlanBuilder
  -> PolicyEngine
  -> AssistantExecutor
  -> deterministic research intelligence tools
  -> GroundednessValidator
  -> AnswerSynthesizer
  -> ResearchAnswerAudit
```

## Proposed modules

```text
vnalpha/assistant/research_intelligence_intents.py
vnalpha/assistant/research_templates.py
vnalpha/assistant/groundedness.py
vnalpha/assistant/research_audit.py
vnalpha/tools/research_intelligence.py
```

## New intents

```text
deep_analyze_symbol
review_market_regime
review_sector_strength
summarize_watchlist_deep
generate_shortlist
generate_research_scenario
review_setup_evidence
```

## New tools

```text
analysis.deep_symbol
market.get_regime
sector.get_strength
sector.get_symbol_alignment
watchlist.summarize_deep
shortlist.generate
scenario.generate_research_plan
evidence.get_setup_history
```

## Planning rules

- Plans must use deterministic tools only.
- Tools must return structured payloads.
- Generated code is not part of this assistant tool layer; route it through sandbox/research automation specs.
- Scenario and shortlist outputs require policy checks before final answer.

## Synthesis templates

Each intent should have a template defining:

```text
required fields
allowed wording
required caveats
missing-data disclosure
grounded source references
```

## Research answer audit

Every deep research answer should persist:

```text
intent
tool outputs used
artifact refs
dataset freshness
groundedness status
policy status
final caveats
correlation_id
```
