# Proposal: TUI Research Workflow Polish

## Summary

Define the OpenSpec for TUI workflows that render deep research intelligence outputs in the opencode-like OpenStock terminal workspace.

This is an OpenSpec-only change.

## Motivation

OpenStock's TUI already has a single composer and output stream. As deeper research objects are added, the TUI must support readable rendering and efficient drilldown without reverting to a dashboard-first or multi-input architecture.

## Scope

Define requirements for TUI rendering and workflows for:

```text
deep symbol analysis
market regime
sector strength
watchlist synthesis
shortlist
research scenario plan
setup historical evidence
research artifacts
long-running workflow status
keyboard drilldown
save note from output
route artifact to assistant
```

## Non-goals

- Do not reintroduce ContentSwitcher as the default workflow.
- Do not add a second primary input.
- Do not add broker/order/account/trading execution controls.
- Do not make TUI panels a blocker for command/assistant functionality.

## Target behavior

The TUI remains composer-first:

```text
single ComposerInput
single primary OutputStream
optional responsive read-only panels
inline command/assistant output
keyboard shortcuts for navigation only
```
