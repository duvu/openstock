# Complete Phases 5.8, 5.9, and 6

## Summary

Add a completion OpenSpec for the current implementation of:

```text
Phase 5.8 — Research Workspace Command Layer
Phase 5.9 — Natural-Language Research Assistant
Phase 6   — Outcome Tracking and Feedback Loop
```

The codebase now contains substantial implementation for all three phases:

```text
vnalpha cmd "<slash-command>"
vnalpha ask "<natural-language question>"
vnalpha outcome ...
TUI command, assistant, and outcome screens
assistant_session / llm_trace tables
candidate_outcome and aggregate outcome tables
```

This change defines the final acceptance gates and remaining fixes required before these phases can be declared complete.

## Motivation

The phases are no longer spec-only, but the current implementation still has gaps that prevent a clean completion call.

Important remaining issues include:

```text
- Phase 5.8 CLI/TUI command execution paths are inconsistent.
- Phase 5.8 TUI command execution does not persist research_session/tool_trace.
- Phase 5.8 command handlers still bypass the LocalToolRegistry in the CLI/TUI command layer.
- /scan still treats universe as informational and does not render risk flags.
- /filter does not reject unsupported/unsafe filter fields.
- Phase 5.9 exists but relies on real LLM config unless tested with fake/stub client.
- Phase 5.9 tool_trace uses session_id to store assistant_session_id, which is ambiguous.
- Phase 6 evaluator persists candidate_outcome but does not automatically generate aggregate outcome tables in the evaluate command path.
- Phase 6 outcome report depends on aggregate tables that may remain empty after evaluation.
- TUI outcome screen may add duplicate columns for no-data states.
```

## Goals

- Define a single completion gate for Phases 5.8, 5.9, and 6.
- Align CLI and TUI behavior across command, assistant, and outcome surfaces.
- Ensure every command/assistant tool call is traceable.
- Ensure Phase 5.9 assistant cannot bypass the Phase 5.8 tool contract.
- Ensure Phase 6 evaluation produces candidate outcomes and aggregate outcomes in one user-facing path.
- Add targeted tests that prove the phases are complete, not just present.
- Preserve research-only boundaries: no trading execution, no account management, no portfolio workflows, no buy/sell instructions.

## Non-goals

- No implementation of Phase 7 Python sandbox.
- No web retrieval or external document fetch.
- No MCP client integration.
- No broker execution or portfolio management.
- No ML ranking.
- No full backtest lab.

## Scope

### In scope

```text
Phase 5.8 command execution consistency
Phase 5.8 tool registry and trace enforcement
Phase 5.8 CLI/TUI persistence parity
Phase 5.9 assistant session, llm_trace, tool_trace, planner, policy, and answer grounding acceptance
Phase 6 candidate outcome, aggregate outcome, report, CLI, and TUI acceptance
Regression tests for Phase 5 E2E
Targeted tests for Phase 5.8, 5.9, and 6
```

### Out of scope

```text
web search
web fetch
Python execution
MCP tools
broker/account/order/portfolio actions
automatic scoring-weight mutation
AI-only signals
```

## Acceptance summary

The phases are complete only when:

```text
- Phase 5.8 command execution uses the same traced execution service in CLI and TUI.
- Phase 5.8 every command and tool call persists trace records.
- Phase 5.8 /scan, /filter, /compare, /explain, /quality, /lineage, /note, /history meet their spec outputs.
- Phase 5.9 `vnalpha ask` and TUI assistant work with a fake LLM in tests and with configured LLM at runtime.
- Phase 5.9 unsafe/unavailable requests are refused before tool execution.
- Phase 5.9 all assistant answers are grounded in tool outputs and expose plan/trace when requested.
- Phase 6 `vnalpha outcome evaluate` produces candidate_outcome and all aggregate tables for configured horizons.
- Phase 6 report and TUI outcome screen work immediately after evaluation.
- Research-only safety boundaries are enforced in outputs and tests.
```
