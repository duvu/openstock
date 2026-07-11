# Assistant research intelligence tools

## Purpose

The research assistant can now route complex research questions to deterministic,
warehouse-grounded tools. The LLM classifies the request and explains tool output;
it does not calculate authoritative scores, levels, rankings, or historical
statistics itself.

## Supported intents

| Intent | Deterministic tool | Purpose |
|---|---|---|
| `deep_analyze_symbol` | `analysis.deep_symbol` | Structured symbol context, levels, quality, lineage, market and sector context |
| `review_market_regime` | `market.get_regime` | Persisted market-regime snapshot |
| `review_sector_strength` | `sector.get_strength` | Persisted ranked sector snapshots |
| `review_symbol_sector_alignment` | `sector.get_symbol_alignment` | Persisted symbol-to-sector alignment |
| `summarize_watchlist_deep` | `watchlist.summarize_deep` | Class/setup/sector distributions and research-focus groups |
| `generate_shortlist` | `shortlist.generate` | Explainable research-priority ranking |
| `generate_research_scenario` | `scenario.generate_research_plan` | Conditional monitoring scenarios for one symbol |
| `review_setup_evidence` | `evidence.get_setup_history` | Persisted setup-outcome statistics |

## Example questions

```text
Give me a deep research review of FPT.
Review the current market regime.
Which persisted sectors rank highest?
Summarize today's watchlist deeply.
Create a five-name research shortlist.
Create a conditional research scenario for FPT.
Review historical evidence for ACCUMULATION_BASE over 20 sessions.
```

## Execution flow

```text
current user request
  -> deterministic safety policy
  -> LLM intent classification
  -> deterministic plan builder
  -> central tool-policy validation
  -> deterministic data provisioning when symbol analysis requires it
  -> local read-only research tools
  -> pre-synthesis payload validation
  -> task-aware LLM synthesis
  -> post-synthesis groundedness and language validation
  -> research_answer_audit persistence
```

## Tool output contract

Research-intelligence payloads use a consistent contract where applicable:

```text
status
as_of_date or requested_date
methodology or methodology_version
freshness
quality
lineage
artifact_refs
caveats
missing_data
```

Status values are descriptive:

```text
READY        required persisted evidence is available
PARTIAL      useful evidence exists but one or more inputs are incomplete
UNAVAILABLE  the required persisted artifact does not exist
```

A missing upstream engine or artifact must not be simulated. The tool returns an
explicit missing-data contract instead.

## Groundedness rules

Before synthesis, the assistant checks:

- the expected tool result exists;
- the primary payload is structured;
- required data keys are present;
- tool warnings and caveats are retained.

After synthesis, the assistant checks:

- quantitative or categorical claims correspond to payload fields;
- partial or unavailable payloads are disclosed in `missing_data`;
- risks and caveats are not empty;
- shortlist and scenario answers remain explicitly research-framed;
- execution-oriented wording is rejected.

A failed groundedness check causes the answer to fail rather than returning an
unsupported claim.

## Research-only boundary

Allowed output includes:

```text
persisted classifications
technical and contextual evidence
support/resistance ranges derived from stored bars
research-priority ranking
conditional confirmation/failure scenarios
historical descriptive outcome statistics
caveats, quality, lineage, and missing data
```

The assistant does not expose broker, account, allocation, unrestricted code,
filesystem, raw SQL, or autonomous data-mutation tools. Data refresh remains an
explicit command or a deterministic analysis precondition.

## Research answer audit

Every completed research-intelligence answer writes one
`research_answer_audit` record with:

```text
assistant session id
intent
tool names
artifact references
dataset freshness
groundedness status and details
policy status
caveats
correlation id
```

A best-effort `RESEARCH_ANSWER_AUDITED` event is also written to file
observability. Raw prompts and full answer text are not duplicated into this audit
record.

## Adapter boundary

Some domain engines are still evolving. The current tools provide stable public
contracts over existing persisted artifacts:

```text
candidate_score
feature_snapshot
canonical_ohlcv
daily_watchlist
market_regime_snapshot
sector_strength_snapshot
candidate_outcome
setup_type_performance
```

A future dedicated deep-analysis, shortlist, scenario, or evidence engine can
replace the adapter internals without changing the assistant intent or tool name.

## Tests

Focused coverage:

```text
tests/test_assistant_research_intelligence.py
tests/test_research_intelligence_tools.py
tests/test_research_groundedness_and_audit.py
tests/test_assistant_research_intelligence_e2e.py
tests/test_research_intelligence_golden.py
```

Required repository validation before merge:

```text
make test-vnalpha
make lint-vnalpha
make verify-r4
packaging/scripts/openstock-verify --ci
```
