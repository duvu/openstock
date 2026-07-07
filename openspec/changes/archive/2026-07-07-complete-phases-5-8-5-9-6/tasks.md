# Tasks: Complete Phases 5.8, 5.9, and 6

## 1. Phase 5.8 command execution parity

- [x] 1.1 Add shared `CommandExecutor` used by both CLI and TUI.
- [x] 1.2 Create `research_session` before parsing where possible.
- [x] 1.3 Persist parse errors as `VALIDATION_ERROR` sessions.
- [x] 1.4 Persist unknown command errors as `VALIDATION_ERROR`, not `FAILED`.
- [x] 1.5 Ensure CLI `vnalpha cmd` uses the shared executor.
- [x] 1.6 Ensure TUI CommandScreen uses the shared executor.
- [x] 1.7 Add tests for CLI/TUI session persistence.

## 2. Phase 5.8 traced tool execution

- [x] 2.1 Add `TracedLocalToolExecutor` around `LocalToolRegistry`.
- [x] 2.2 Ensure every command handler calls local tools through traced execution.
- [x] 2.3 Remove direct tool implementation calls from command handlers or wrap them behind the executor.
- [x] 2.4 Persist successful `tool_trace` rows for every tool call.
- [x] 2.5 Persist failed `tool_trace` rows with error metadata.
- [x] 2.6 Add tests proving `/scan`, `/explain`, `/quality`, and `/lineage` create tool traces.

## 3. Phase 5.8 command behavior fixes

- [x] 3.1 Fix parser to reject malformed filters such as `/filter score>>0.70`.
- [x] 3.2 Add filter field allowlist validation.
- [x] 3.3 Reject unsupported filter fields such as `raw_sql` with `VALIDATION_ERROR`.
- [x] 3.4 Implement `/scan VN30` as real universe resolution/filtering or explicitly remove universe syntax from spec/help.
- [x] 3.5 Render `risk_flags` in `/scan` output.
- [x] 3.6 Extend `/compare` output with risk flags, data quality, and relative strength fields when available.
- [x] 3.7 Extend `/explain` output with data quality.
- [x] 3.8 Extend `/quality SYMBOL` output with `rejected_symbol` records.
- [x] 3.9 Add command behavior tests for all fixes above.

## 4. Phase 5.9 assistant completion

- [x] 4.1 Add tests for `vnalpha ask` using `FakeLLMClient` or monkeypatched gateway.
- [x] 4.2 Ensure tests never require external LLM credentials.
- [x] 4.3 Persist `assistant_session` for success, refusal, validation error, and failure.
- [x] 4.4 Persist `llm_trace` for classify and synthesize stages, including model/usage where available.
- [x] 4.5 Add explicit `assistant_session_id` to `tool_trace` or otherwise document and test the parent id mapping.
- [x] 4.6 Ensure `--no-execute` creates no tool_trace.
- [x] 4.7 Ensure `--show-plan` renders stable plan text.
- [x] 4.8 Ensure `--trace` renders executed tool trace summary.
- [x] 4.9 Ensure unsafe prompts are refused before tool execution.
- [x] 4.10 Ensure answers do not override tool output score/class/setup/quality.
- [x] 4.11 Add TUI assistant smoke tests.

## 5. Phase 6 outcome completion

- [x] 5.1 Ensure `vnalpha outcome evaluate` generates candidate outcomes and aggregate outcome tables.
- [x] 5.2 Call `aggregate_all` for each evaluated horizon after candidate outcomes are persisted.
- [x] 5.3 Ensure `outcome report` works immediately after `outcome evaluate`.
- [x] 5.4 Ensure `outcome report` computes missing aggregates or clearly reports missing aggregate data.
- [x] 5.5 Fix CLI/TUI labels from `horizon {n}d` to `horizon {n} sessions`.
- [x] 5.6 Fix OutcomeScreen no-data table behavior to avoid duplicate column-add errors.
- [x] 5.7 Add tests for complete, pending, partial, missing-data, and error statuses.
- [x] 5.8 Add tests for watchlist, score bucket, setup type, and risk flag aggregation.
- [x] 5.9 Add tests for calibration report after evaluation.
- [x] 5.10 Add TUI outcome smoke tests.

## 6. Regression and safety validation

- [x] 6.1 Run Phase 5 E2E fixture tests.
- [x] 6.2 Run Phase 5.8 command-layer tests.
- [x] 6.3 Run Phase 5.9 assistant tests.
- [x] 6.4 Run Phase 6 outcome tests.
- [x] 6.5 Run `cd vnalpha && pytest -q`.
- [x] 6.6 Add tests banning broker/order/account/portfolio/buy/sell wording in command, assistant, and outcome outputs.
- [x] 6.7 Add test that no command/assistant/outcome path mutates scoring weights automatically.

## 7. Manual smoke tests

- [x] 7.1 Run:

```bash
vnalpha cmd "/help"
vnalpha cmd "/scan VN30"
vnalpha cmd "/filter score>=0.70 setup=ACCUMULATION_BASE"
vnalpha cmd "/explain FPT"
vnalpha cmd "/quality FPT"
vnalpha cmd "/lineage FPT"
```

- [x] 7.2 Run:

```bash
vnalpha ask "Show strongest VN30 candidates today" --show-plan --trace
vnalpha ask "Why is FPT in the watchlist?" --show-plan --trace
vnalpha ask "Compare FPT, VNM, and MWG" --show-plan --trace
vnalpha ask "Buy FPT now"
```

The final command must be refused.

- [x] 7.3 Run:

```bash
vnalpha outcome evaluate --date 2026-07-06
vnalpha outcome candidates --date 2026-07-06 --horizon 20
vnalpha outcome watchlist --date 2026-07-06 --horizon 20
vnalpha outcome buckets --horizon 20
vnalpha outcome setups --horizon 20
vnalpha outcome risks --horizon 20
vnalpha outcome report --horizon 20
```

- [x] 7.4 Open TUI and verify:

```text
Command screen
Assistant screen
Outcome Review screen
No-data states
Error/refusal states
```
