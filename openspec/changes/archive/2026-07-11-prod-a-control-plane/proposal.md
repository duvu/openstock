# Proposal: Production control plane for opencode-like auto research

## Summary

Harden the current opencode-like TUI refactor into a production-grade control plane for OpenStock / vnalpha.

This change focuses on the first production phase of the auto research workspace:

```text
Phase A: Foundation / Control Plane
```

The goal is to make the single composer path reliable enough for production use before adding sandbox compute or autonomous research loops.

## Why

The current TUI visual refactor is close to the intended opencode-like workspace, but the functional command path is not production-ready.

Known issues to address:

- `TuiInputRouter._setup_executor()` currently instantiates `CommandExecutor` with the wrong constructor shape.
- `/logs`, `/repair`, and `/deploy` are documented for composer usage but are not bridged as production operational commands.
- Slash command lifecycle logging is not yet a first-class TUI path.
- ChatController callbacks can call Textual widgets from worker threads.
- Tests patch around the broken executor path and therefore do not catch real command routing failure.

Production MVP2 must first establish a reliable control plane:

```text
single composer input
  -> route
  -> plan / command / chat / operational command
  -> execute with lifecycle logging
  -> render inline
  -> persist audit / trace / error evidence
```

## Goals

- Fix TUI slash command routing using the real `CommandExecutor(conn, surface="tui", default_date=...)` contract.
- Keep and close a DuckDB connection owned by the TUI router or an explicit router lifecycle object.
- Bridge `/logs`, `/repair`, and `/deploy` into the composer path.
- Emit command lifecycle observability for every slash command submitted via TUI.
- Ensure UI updates from chat/tool callbacks are marshalled safely onto the Textual app loop.
- Add tests that exercise the real router setup instead of patching away executor construction.
- Preserve the read-only research boundary.
- Preserve closed-loop logging.
- Preserve redaction-by-default.

## Non-goals

- No sandbox code execution in this phase.
- No backtest or feature-engineering automation in this phase.
- No broker, order, account, portfolio, margin, or trading execution integration.
- No reintroduction of `ContentSwitcher` or persistent secondary `ChatPanel` in the default TUI path.
- No business logic rewrite for scoring, watchlist, quality, lineage, notes, repair, or deploy.

## Scope

### Production TUI router

`TuiInputRouter` SHALL be the production control-plane router for the default TUI path.

It SHALL support:

```text
/plain-language question
/research-command
/logs ...
/repair ...
/deploy ...
/approve
/cancel
/clear
```

### CommandExecutor lifecycle

The router SHALL initialize `CommandExecutor` with:

```python
CommandExecutor(conn, surface="tui", default_date=target_date)
```

The router SHALL:

- open a DuckDB connection using the repo warehouse connection factory;
- run migrations before command execution;
- keep the connection available for command execution;
- close the connection during router/app shutdown;
- fail inline with actionable error messages if setup fails.

### Operational command bridge

The composer path SHALL support these operational commands at minimum:

```text
/logs errors --latest
/logs summarize --latest
/repair prepare --latest
/repair status <repair-id>
/deploy verify <candidate>
/deploy promote <candidate> --deployment-id <id>
/deploy rollback <deployment-id>
```

If a subcommand is not yet implemented, the TUI SHALL render a clear unsupported message and log the route attempt.

`/deploy` in OpenStock means research artifact verification/promotion/rollback. It SHALL NOT mean broker execution or trading deployment.

### Observability

Every TUI command route SHALL emit lifecycle evidence:

```text
TUI_INPUT_SUBMITTED
TUI_COMMAND_ROUTED
COMMAND_STARTED
COMMAND_SUCCEEDED
COMMAND_FAILED
TUI_RENDER_ERROR when applicable
```

Events SHALL include a non-empty correlation ID and preserve redaction-by-default.

### Thread safety

ChatController and tool trace callbacks invoked from worker threads SHALL NOT call Textual widgets directly.

The implementation SHALL marshal UI updates through a safe Textual app mechanism, message queue, or call-from-thread bridge.

## Success criteria

This change is complete only when:

```text
- `vnalpha tui` still mounts exactly one OutputStream and one ComposerInput.
- The default DOM still has exactly one Textual Input.
- `/help` through TUI uses a real CommandExecutor setup and renders into OutputStream.
- `/logs errors --latest` is routed through the operational bridge.
- `/repair prepare --latest` is routed through the operational bridge.
- `/deploy verify <candidate>` is routed through the operational bridge.
- Slash command execution emits lifecycle observability.
- Chat callback rendering has no cross-thread UI mutation path.
- Router/app shutdown closes owned DuckDB connection.
- All command failures render inline and are captured.
- read-only research boundary is preserved.
```

## Validation commands

Run:

```bash
make test-vnalpha
make lint-vnalpha
make verify-r4
openstock-verify --ci
```

## Production boundary

This phase is allowed to improve command routing, logs, repair, deploy verification, and observability.

It SHALL NOT add or imply any broker, order, account, portfolio, margin, allocation, or trading execution feature.

Use the phrase `read-only research boundary` in code comments, docs, and tests where the boundary is relevant.
