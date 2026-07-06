# Add Phase 5.8 Research Workspace Command Layer

## Summary

Add an OpenSpec change for Phase 5.8: Research Workspace Command Layer.

Phase 5 already establishes the deterministic pipeline and TUI surface:

```text
vnstock-service
→ vnalpha sync
→ DuckDB warehouse
→ canonical OHLCV
→ feature store
→ scoring engine
→ daily watchlist
→ TUI workspace
```

Phase 5.8 adds the interaction layer that turns `vnalpha` from a pipeline/TUI into a command-driven research workspace.

The new layer provides:

```text
slash command parser
command registry
local tool registry
research session history
tool trace persistence
command result rendering
TUI command input surface
```

## Motivation

The Phase 5 MVP can produce a daily watchlist, but users still need to run fixed commands or inspect fixed screens.

A research workspace needs a controlled way to ask follow-up questions such as:

```text
/scan VN30
/filter score>=0.70 setup=ACCUMULATION_BASE
/compare FPT VNM MWG
/explain FPT
/quality FPT
/lineage FPT
/note FPT "watch relative strength vs VNINDEX"
```

This should exist before the natural-language assistant in Phase 5.9. The LLM layer should call typed command/tools, not free-form internal functions.

## Goals

- Define a deterministic slash-command grammar for Phase 5.8.
- Define command and tool registry boundaries.
- Persist research sessions and tool traces.
- Render command results consistently in CLI/TUI.
- Preserve research-only safety boundaries.
- Prepare a stable tool contract for Phase 5.9 natural-language routing.

## Non-goals

- No LLM planning in Phase 5.8.
- No Python sandbox execution in Phase 5.8.
- No web retrieval in Phase 5.8.
- No broker/account/order/portfolio integration.
- No buy/sell recommendation workflow.
- No autonomous trading behavior.

## Scope

### In scope

```text
Command parser
Command registry
Local tool registry
Research session store
Tool trace store
Command result model
CLI command runner
TUI command input and output panel
Initial slash commands
```

Initial commands:

```text
/scan
/filter
/compare
/explain
/quality
/lineage
/note
/help
/history
```

### Out of scope

```text
/ask natural-language assistant
/python sandbox
/search web retrieval
/fetch external document retrieval
/backtest lab
/outcome tracking
MCP client integration
```

These belong to later phases.

## User impact

Users can move from a static watchlist review flow to an interactive research workflow without enabling AI planning yet.

Example workflow:

```text
/scan VN30
/filter score>=0.70 class=STRONG_CANDIDATE
/explain FPT
/quality FPT
/lineage FPT
/note FPT "strong candidate but check liquidity and index context"
```

Every command is recorded, every tool call is traceable, and every output can be reproduced from warehouse state.

## Safety impact

Phase 5.8 keeps all execution deterministic:

```text
command text
→ parser
→ command registry
→ allowed local tool
→ warehouse query / deterministic renderer
```

The command layer must not allow arbitrary SQL, arbitrary file access, generated Python, internet access, LLM-only signals, or trading execution.

## Acceptance summary

The change is complete when:

```text
- slash commands are parsed deterministically.
- command registry rejects unknown commands.
- commands call only typed local tools.
- every command writes a research_session entry.
- every local tool call writes a tool_trace entry.
- command outputs render consistently in CLI/TUI.
- TUI exposes a command input surface and result panel.
- no trading execution or recommendation language is introduced.
```
