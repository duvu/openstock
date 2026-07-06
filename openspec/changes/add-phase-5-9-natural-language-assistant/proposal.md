# Add Phase 5.9 Natural-Language Research Assistant

## Summary

Add an OpenSpec change for Phase 5.9: Natural-Language Research Assistant.

Phase 5 creates the deterministic alpha discovery pipeline and TUI. Phase 5.8 introduces the command/tool layer. Phase 5.9 adds a natural-language interface that maps user research questions to approved deterministic commands and local tools.

The assistant is a planner, router, explainer, critic, and summarizer. It is not a scoring authority and must not generate independent trading signals.

## Motivation

After Phase 5.8, the user can interact with `vnalpha` using commands such as:

```text
/scan VN30
/filter score>=0.70 setup=ACCUMULATION_BASE
/explain FPT
/quality FPT
/lineage FPT
```

Phase 5.9 lets the user ask the same thing naturally:

```text
Show me the strongest VN30 candidates today and explain the main risks.
Compare FPT, VNM, and MWG using the latest score, setup, risk flags, and data quality.
Why is FPT in the watchlist today?
Which candidates have weak data quality?
```

The assistant must translate these requests into typed tool/command calls and return grounded answers with traceability.

## Goals

- Add a natural-language prompt surface for research questions.
- Classify user intent into supported research actions.
- Build explicit tool plans from approved Phase 5.8 command/tool capabilities.
- Execute only allowlisted tools.
- Ground answers in deterministic artifacts: watchlist, candidate score, features, quality, lineage, notes, and history.
- Persist assistant sessions, model traces, tool traces, and final answers.
- Expose the plan and executed tools to the user.
- Refuse unsupported, unsafe, or trading-execution requests.

## Non-goals

- No AI-only scoring.
- No LLM override of deterministic score or candidate class.
- No broker/order/account/portfolio execution.
- No autonomous trading.
- No unrestricted SQL.
- No generated Python execution.
- No direct internet access from the LLM.
- No MCP tool calls in this phase.
- No dynamic web retrieval unless a later retrieval phase has provided approved retrieval tools and permissions.

## Scope

### In scope

```text
Natural-language prompt parser
Intent classifier
Plan builder
Tool-call planner
Tool allowlist enforcement
Plan preview and trace
Grounded answer synthesizer
Refusal policy
Assistant session persistence
LLM request/response trace metadata
CLI ask command
TUI ask input surface
```

Initial intent families:

```text
scan_candidates
filter_candidates
compare_symbols
explain_symbol
review_quality
show_lineage
summarize_watchlist
create_research_note
show_history
unsupported_or_unsafe
```

### Out of scope

```text
web search/fetch
Python research sandbox
MCP client
backtest lab
outcome tracking
codebase mutation
broker execution
portfolio workflows
```

These are separate later phases.

## User impact

Users can ask research questions without memorizing command syntax, while still benefiting from deterministic, auditable tool execution.

Example:

```text
User: Compare FPT, VNM, and MWG and tell me which one has the cleaner setup.
Assistant plan:
1. Call candidate.compare for FPT, VNM, MWG.
2. Call quality.get_status for FPT, VNM, MWG.
3. Call lineage.get_symbol_lineage for each symbol.
4. Synthesize a comparison grounded in scores, setup types, risk flags, and quality.
```

The final answer must show the basis of the conclusion and must not turn the comparison into a buy/sell instruction.

## Safety impact

Phase 5.9 introduces LLM use, so the boundary must be stricter than Phase 5.8.

The assistant must:

```text
- treat deterministic warehouse artifacts as source of truth.
- expose tool calls and assumptions.
- refuse trading execution and account/portfolio requests.
- never claim certainty or guaranteed prediction.
- never invent source data not returned by tools.
- never override persisted candidate_score.
- never call unavailable tools.
```

## Acceptance summary

The change is complete when:

```text
- user can ask natural-language research questions through CLI/TUI.
- each request is classified into a supported intent or refused.
- assistant creates an explicit tool plan.
- assistant executes only allowlisted local tools.
- answers are grounded in tool outputs and deterministic artifacts.
- assistant sessions and LLM/tool traces are persisted.
- unsafe requests fail closed.
- no order/account/portfolio/buy/sell recommendation behavior is introduced.
```
