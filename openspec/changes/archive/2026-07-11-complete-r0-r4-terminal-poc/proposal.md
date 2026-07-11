# Proposal: Complete R0-R4 Terminal POC

## Summary

Complete the OpenStock terminal-first POC across roadmap phases R0 through R4.

This change is a completion gate, not a new feature direction. It converts the current partially implemented and partially documented state into an executable, test-backed, deployable MVP slice:

```text
R0 — POC Baseline Stabilization
R1 — POC Deployment Architecture
R2 — Deploy & Verify POC
R3 — Terminal Workspace POC
R4 — OpenCode-style Chat Workspace Completion
```

The result should be a repeatable local-first research system:

```text
vnstock-service  -> data-only Docker service
vnalpha-worker   -> Docker batch/job pipeline
DuckDB warehouse -> persisted analytical warehouse
vnalpha.deb      -> host-native CLI/TUI terminal workspace
ChatPanel        -> persistent research chat/control panel
```

## Why

The current codebase already contains meaningful implementation for the research pipeline, CLI, warehouse schema, data service, scoring, watchlist, TUI entrypoint, command layer, assistant layer, outcome tables, and deployment documentation.

However, R0-R4 should not be declared complete until the implementation is verified end-to-end through executable commands and tests. Previous documentation/spec PRs captured requirements but did not consistently prove runtime completion.

This change closes that gap by defining a single acceptance boundary for the first usable MVP.

## Goals

- Finish the deterministic alpha-discovery baseline.
- Keep `vnstock` data-only and research-safe.
- Make POC deployment repeatable on a fresh host.
- Make verification explicit through `openstock-verify` and CI-safe checks.
- Make `vnalpha tui` the primary terminal workspace.
- Complete the persistent ChatPanel as a research control panel.
- Preserve research-only boundaries: no broker login, account APIs, order placement, portfolio execution, margin, transfer, auto-trading, or LLM-only prediction.

## Non-goals

- No broker integration.
- No trading execution.
- No portfolio mutation.
- No public web service exposure by default.
- No multi-user production deployment.
- No ML ranking model.
- No backtest lab beyond smoke-level outcome/evaluation compatibility.
- No arbitrary shell execution from chat.
- No `vnalpha serve` local runtime/server; that starts at R5.

## Scope

### R0 — POC Baseline Stabilization

- Fresh DuckDB initialization.
- Data sync command contract.
- VN30 universe handling.
- VNINDEX benchmark handling.
- Canonical OHLCV build.
- Feature snapshot build.
- Candidate scoring and daily watchlist generation.
- Quality, lineage, date, ontology, and regression hardening.
- Fixture-backed E2E test.

### R1 — POC Deployment Architecture

- Finalize and align deployment docs with actual files.
- Make architecture decisions executable, not only descriptive.
- Preserve single-host localhost-first deployment model.

### R2 — Deploy & Verify POC

- Top-level Docker Compose data platform.
- `vnalpha-worker` image.
- Debian package for terminal app.
- `/usr/bin/vnalpha` and `/usr/bin/vnalpha-poc` launchers.
- `/etc/vnalpha/vnalpha.env` and `/etc/openstock/openstock.env` config.
- systemd wrapper.
- post-deploy verification.
- backup/rollback.
- writer lock for pipeline jobs.

### R3 — Terminal Workspace POC

- Persistent terminal workspace layout.
- Watchlist, symbol detail, quality, rejected data, outcomes/calibration panels.
- Command palette/slash command help.
- Keyboard shortcuts.
- Read-only demo mode.
- TUI smoke tests.

### R4 — OpenCode-style Chat Workspace Completion

- Persistent ChatPanel.
- `chat_session` and `chat_message` usage.
- Multi-turn deterministic context.
- Unified command execution path.
- Plan preview/approve/cancel.
- Tool trace timeline.
- Chat-local commands.
- Research-only hard-deny enforcement.

## Success criteria

R0-R4 are complete only when all of the following are true:

```text
make test-vnalpha                         passes
make lint-vnalpha                         passes or documented lint exceptions are explicit
pytest fixture E2E                        passes without network access
docker compose config                     passes
docker compose up -d vnstock-service      starts localhost-only data service
docker compose --profile job run ...      can run init/sync/build/score/watchlist smoke flow
vnalpha.deb                               builds and installs
vnalpha --help                            works after package install
vnalpha tui --date <demo-date>            starts from host terminal
openstock-verify                          passes required checks
openstock-backup-warehouse                creates timestamped backup
TUI smoke tests                            cover construction/navigation
ChatPanel tests                            cover persistence/context/commands/plan/trace/safety
```

## Risks

- DuckDB writer concurrency can corrupt demo reliability if pipeline jobs overlap.
- TUI tests may be flaky if they launch a fully interactive app instead of app construction or pilot mode.
- ChatPanel can drift into a parallel command path unless command execution is centralized.
- Documentation-only checklists can be mistaken for runtime completion.

## Mitigations

- Add writer locks for pipeline, backup, and scheduled jobs.
- Add CI-safe verification mode that avoids live provider calls.
- Test TUI entrypoint non-interactively.
- Make `openstock-verify` the authoritative post-deploy gate.
- Treat OpenSpec task completion as valid only when backed by code, tests, or runnable scripts.
