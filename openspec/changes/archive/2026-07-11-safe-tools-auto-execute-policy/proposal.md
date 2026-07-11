# Proposal: Safe Tools Auto-Execute Policy and TUI Command Lifecycle

## Summary

Introduce a single `SAFE_TOOLS` source of truth for the vnalpha assistant/TUI execution boundary. All tools listed in `SAFE_TOOLS` execute automatically. Tools outside `SAFE_TOOLS` are refused. Broker/order/account/portfolio/margin/trading execution remains permanently forbidden.

This change also specifies the missing TUI operational command bridge for `/logs`, `/repair`, and `/deploy`, plus command lifecycle logging for all slash/operational commands submitted from the TUI.

## Motivation

Recent TUI review found that the visual opencode-like workspace is close to target, but functional integration is incomplete:

- Multiple tool allowlists exist with diverging semantics.
- `SAFE_READ_ONLY_TOOLS` does not match planner/executor allowlists.
- The desired product behavior is not approval-gated execution; it is auto-execution for trusted internal research tools.
- `/logs`, `/repair`, and `/deploy` are documented but not actually bridged by `TuiInputRouter`.
- TUI slash commands do not consistently preserve `COMMAND_STARTED`, `COMMAND_SUCCEEDED`, and `COMMAND_FAILED` lifecycle events.
- TUI chat callbacks risk updating Textual widgets from a worker thread.
- The router keeps a DuckDB-backed command executor but does not expose an explicit close lifecycle.
- Some tests and docs overclaim behavior, especially `vnalpha tui --smoke` and logs/repair/deploy support.

## Scope

In scope:

- Define single `SAFE_TOOLS` policy module.
- Make planner, executor, and chat safety consume the same policy.
- Preserve automatic execution for every tool in `SAFE_TOOLS`.
- Preserve hard-deny for any future broker/order/account/portfolio/margin/trading execution tool.
- Add explicit `/logs`, `/repair`, `/deploy` TUI routing bridge.
- Add lifecycle observability for all TUI slash/operational commands.
- Add TUI router close lifecycle for DuckDB connection cleanup.
- Add Textual-safe UI dispatch for worker-thread callbacks.
- Align docs/tasks/tests with implemented behavior.

Out of scope:

- Broker integration.
- Order placement.
- Account/portfolio/margin management.
- Trading execution.
- Internet trading signals, broker APIs, or live execution automation.

## Policy Decision

The system is an internal research workspace. It may auto-execute trusted local research tools, including internal workspace writes such as `note.create` and data provisioning such as `data.fetch`.

The safety boundary is not "read-only only". The safety boundary is:

> only trusted `SAFE_TOOLS` may execute; broker/order/account/portfolio/margin/trading execution never executes.

This preserves the read-only research boundary in the product sense: OpenStock remains a research-only system and does not expand into trading execution.

## Affected Areas

- `vnalpha.assistant` policy/planner/executor modules
- `vnalpha.chat` execution mode and plan safety handling
- `vnalpha.tui.input_router`
- `vnalpha.tui.app`
- TUI output/status dispatch
- TUI docs and OpenSpec task tracking
- tests for assistant safety, TUI routing, lifecycle logging, and docs claims

## Success Criteria

- Exactly one policy source defines safe executable tools.
- Any tool in `SAFE_TOOLS` auto-executes in normal assistant/TUI mode.
- Any tool not in `SAFE_TOOLS` is refused.
- Broker/order/account/portfolio/margin/trading execution tools are hard-denied even if introduced later.
- `/logs`, `/repair`, and `/deploy` are routed explicitly by TUI and no longer fall through to research command registry.
- Every TUI slash/operational command emits command lifecycle events.
- TUI chat callbacks are marshalled onto the Textual app loop.
- DuckDB command connection is closed on TUI shutdown.
- Documentation matches actual code behavior.

## Validation Commands

```bash
make test-vnalpha
make lint-vnalpha
make verify-r4
openstock-verify --ci
```
