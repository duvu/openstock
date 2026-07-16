## Why

The MVP1 chat vertical slice is now implemented across provisioning (#163),
symbol-knowledge projection (#164), the LLM route preflight (#165) and one-command
startup/preflight (#166). What remains is proof: an automated acceptance test that
drives the complete user flow on the real code path from an empty warehouse.

Issue #167 adds that golden end-to-end acceptance test and release gate.

## What Changes

- add one golden conversation acceptance test,
  `tests/test_issue_167_golden_conversation.py`, that from an empty in-memory
  warehouse and empty symbol-knowledge directory drives the REAL planner,
  provisioning operation, canonical/feature/scoring builders, deep analysis,
  synthesis, groundedness, research audit and symbol-knowledge projection — with
  a fake LLM and a call-counting fixture at the network-fetch boundary only:
  - turn 1: NL `Phân tích FPT` provisions (symbols, FPT OHLCV, VNINDEX), builds
    canonical/features/score, persists evidence, returns a grounded answer with
    as-of/evidence/freshness/caveats and the provisioning+analysis trace, and
    projects deterministic symbol knowledge whose value matches the persisted
    score (no chat/model prose promoted);
  - turn 2: a follow-up reuses fresh warehouse + knowledge with zero new provider
    fetches and idempotent projection;
  - refresh: an explicit refresh threads force-refresh and discloses bounded
    actions;
  - failure: a service-unavailable fixture fails closed with an actionable typed
    outcome and promotes no partial/corrupt evidence;
  - parity: the shared `ensure_current_symbol_ready` operation that `/analyze`
    invokes reuses the same persisted evidence the NL turn produced.

## Capabilities

### Added Capabilities

- `mvp1-golden-acceptance`: an automated golden conversation proving the MVP1
  chat vertical slice end to end on the real code path, and the release gate.

## Impact

- test in `vnalpha/tests/test_issue_167_golden_conversation.py`;
- no runtime/source change — this is an acceptance/gate addition;
- runs under `make test-vnalpha` (the required CI gate). Out of scope:
  historical/adjusted-price research, Backtest Lab, fundamentals, document/news
  intelligence, licensed providers, multi-user hosting and execution features.
