# Tasks: Deep Symbol Analysis Engine

## 0. Governance

- [ ] 0.1 Keep outputs research-only.
- [ ] 0.2 Do not produce buy/sell/order/allocation/account/broker/margin instructions.
- [ ] 0.3 Include caveats and missing-data disclosure.

## 1. Models and persistence

- [ ] 1.1 Reuse or add `SetupAnalysis` persistence.
- [ ] 1.2 Reuse or add `SymbolLevelSnapshot` persistence.
- [ ] 1.3 Add `DeepSymbolAnalysis` contract.
- [ ] 1.4 Persist analysis artifact references.

## 2. Builders

- [ ] 2.1 Add `DeepAnalysisBuilder`.
- [ ] 2.2 Add `LevelExtractor`.
- [ ] 2.3 Add `SetupQualityEvaluator`.
- [ ] 2.4 Add `ConfidenceEvaluator`.
- [ ] 2.5 Add context assembler.

## 3. Feature/context blocks

- [ ] 3.1 Build trend context.
- [ ] 3.2 Build momentum context.
- [ ] 3.3 Build relative strength context.
- [ ] 3.4 Build volume context.
- [ ] 3.5 Build volatility context.
- [ ] 3.6 Build support/resistance context.
- [ ] 3.7 Build setup quality context.
- [ ] 3.8 Build caveated scenario summary.

## 4. Commands and tools

- [ ] 4.1 Add `/analyze SYMBOL`.
- [ ] 4.2 Add `analysis.deep_symbol` tool.
- [ ] 4.3 Add assistant intent `deep_analyze_symbol`.
- [ ] 4.4 Add synthesis template.
- [ ] 4.5 Add help/docs examples.

## 5. Deep-analysis readiness

- [ ] 5.1 Define typed deep-analysis readiness request/result models with per-artifact status, requested/resolved as-of dates, actions, freshness, lineage, warnings, errors, and correlation ID.
- [ ] 5.2 Extend deterministic ensure-data to evaluate and provision `market_regime_snapshot` and `sector_strength_snapshot` after symbol, benchmark, feature, and score readiness.
- [ ] 5.3 Keep one-symbol provisioning minimal and do not trigger a full-universe refresh unless an explicit market/sector context build requires its bounded input set.
- [ ] 5.4 Invoke deep readiness before `/analyze` and before `analysis.deep_symbol` in the assistant executor.
- [ ] 5.5 Fail the bounded execution path when a required readiness action fails; do not log-and-continue past a failed precondition.
- [ ] 5.6 Preserve explicit missing-data disclosure only for optional/genuinely unavailable context and render deterministic readiness evidence.
- [ ] 5.7 Emit correlated audit events for start, artifact decision/action, cache hit, partial, failure, and completion.

## 6. Explicit data provisioning commands

- [ ] 6.1 Add a shared deterministic command service that reuses existing ingestion, canonical, feature, score, regime, and sector builders.
- [ ] 6.2 Add CLI `vnalpha data download` subcommands for `symbols`, one-symbol `ohlcv`, and `index`.
- [ ] 6.3 Add CLI `vnalpha data build` subcommands for `canonical`, `features`, `score`, `market-regime`, and `sector-strength`.
- [ ] 6.4 Add matching TUI `/data download` and `/data build` forms, help metadata, validation, and readiness rendering.
- [ ] 6.5 Retain existing `sync` and `build` CLI commands without duplicating provider I/O or bypassing policy.
- [ ] 6.6 Document data types, provider options, output, failure diagnostics, and the research-only boundary.

## 7. Tests

- [ ] 7.1 Test analysis output contains all required blocks.
- [ ] 7.2 Test missing data caveats.
- [ ] 7.3 Test level extraction output.
- [ ] 7.4 Test setup quality decomposition.
- [ ] 7.5 Test assistant route.
- [ ] 7.6 Test no trading/execution language.
- [ ] 7.7 Test deep analysis provisions missing market-regime and sector-strength snapshots before the read tool runs.
- [ ] 7.8 Test fresh deep inputs produce cache-hit readiness actions only.
- [ ] 7.9 Test a failed required precondition prevents `analysis.deep_symbol` execution and returns an actionable structured status.
- [ ] 7.10 Test optional unavailable context is explicitly disclosed and cannot render as current.
- [ ] 7.11 Test each CLI and TUI data command parses valid input, rejects invalid input, reuses the shared service, and reports correlated status.
- [ ] 7.12 Test the assistant plan remains read-only and cannot directly plan or call `data.fetch`.

## 8. Validation

- [ ] 8.1 Run `make test-vnalpha`.
- [ ] 8.2 Run `make lint-vnalpha`.
- [ ] 8.3 Run `make verify-r4`.
- [ ] 8.4 Run `openstock-verify --ci`.
- [ ] 8.5 Run focused data-availability, assistant-executor, deep-analysis, CLI, and TUI tests, including a mocked end-to-end missing-context path.
- [ ] 8.6 Run `uv run vnalpha data --help`, one valid manual-fixture path, and one invalid-input path as manual QA evidence.
- [ ] 8.7 Record exact command outcomes and runtime-log references in `validation.md`; do not claim unrun checks passed.
