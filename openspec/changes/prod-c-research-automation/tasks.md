# Tasks: Research automation for opencode-like auto research

## 0. Governance

- [x] 0.1 Keep all research automation inside the no-trading-execution boundary.
- [x] 0.2 Do not introduce broker, order, account, portfolio, margin, transfer, allocation, or trading execution tools.
- [x] 0.3 Label offline backtest-like workflows as offline research event studies, not live trading workflows.
- [x] 0.4 Preserve redaction-by-default logging.
- [x] 0.5 Persist lineage and reproducibility evidence for every research artifact.
- [x] 0.6 Do not present research output as personalized financial advice.
- [x] 0.7 Require sandbox execution for generated research code.
- [x] 0.8 Require explicit approval before executing generated sandbox code.
- [x] 0.9 Do not implement all research automation commands in one large PR; use implementation slices.

## 1. Research automation models

- [x] 1.1 Add `ResearchArtifact` model.
- [x] 1.2 Add `ResearchExperiment` model or equivalent.
- [x] 1.3 Add `ResearchFeature` model or equivalent.
- [x] 1.4 Add `ResearchHypothesis` model or equivalent.
- [x] 1.5 Add `PatternScan` model or equivalent.
- [x] 1.6 Add `OfflineEventStudy` model or equivalent.
- [x] 1.7 Add `DatasetRef` model.
- [x] 1.8 Add `ArtifactOutputs` model.
- [x] 1.9 Add lineage, quality status, dataset references, and correlation ID fields.
- [x] 1.10 Add artifact statuses: `created`, `running`, `succeeded`, `failed`, `rejected`, `validated`, `promoted`.

## 2. Persistence and artifact layout

- [x] 2.1 Add warehouse migrations for research automation metadata if database-backed.
- [x] 2.2 Persist experiment definitions.
- [x] 2.3 Persist feature definitions.
- [x] 2.4 Persist hypothesis definitions.
- [x] 2.5 Persist pattern scan definitions.
- [x] 2.6 Persist event-study definitions.
- [x] 2.7 Persist result artifacts under `logs/runs/<run-id>/research/<artifact-id>/` or equivalent.
- [x] 2.8 Persist `manifest.json`.
- [x] 2.9 Persist `result.json`.
- [x] 2.10 Persist `summary.md`.
- [x] 2.11 Persist `lineage.json`.
- [x] 2.12 Persist `validation.json`.
- [x] 2.13 Persist generated code path when sandbox code is generated.
- [x] 2.14 Persist reproducibility manifest.

## 3. Command surface

- [x] 3.1 Add `/experiment indicator <description> [--universe UNIVERSE] [--start YYYY-MM-DD] [--end YYYY-MM-DD]`.
- [x] 3.2 Add `/experiment backtest <event-study-description> [--horizon N] [--start YYYY-MM-DD] [--end YYYY-MM-DD]` and render it as an offline research event study.
- [x] 3.3 Add `/feature create <definition>`.
- [x] 3.4 Add `/feature validate <feature-id-or-name>`.
- [x] 3.5 Add `/hypothesis test <hypothesis-text>`.
- [x] 3.6 Add `/pattern scan <pattern-description> [--universe UNIVERSE] [--date YYYY-MM-DD]`.
- [x] 3.7 Render unsupported subcommands inline.
- [x] 3.8 Emit command lifecycle events for every research automation command.
- [x] 3.9 Add command help output for all research automation commands.
- [x] 3.10 Ensure command examples use Vietnamese equity symbols/universes, not US examples.

## 4. Assistant planning

- [x] 4.1 Extend intent classification for `create_indicator_experiment`.
- [x] 4.2 Extend intent classification for `create_feature`.
- [x] 4.3 Extend intent classification for `validate_feature`.
- [x] 4.4 Extend intent classification for `test_hypothesis`.
- [x] 4.5 Extend intent classification for `scan_pattern`.
- [x] 4.6 Extend intent classification for `run_offline_event_study`.
- [x] 4.7 Build deterministic plan templates for each supported research automation intent.
- [x] 4.8 Resolve dataset snapshot and universe before computation.
- [x] 4.9 Require sandbox approval when generated code execution is needed.
- [x] 4.10 Refuse or mark unsupported requests that imply live trading or execution.
- [x] 4.11 Add plan preview that shows dataset refs, generated-code summary, expected artifacts, and caveats.

## 5. Dataset resolution

- [x] 5.1 Add `DatasetResolver` or equivalent.
- [x] 5.2 Resolve symbol universe.
- [x] 5.3 Resolve date range.
- [x] 5.4 Resolve interval.
- [x] 5.5 Resolve benchmark index such as VNINDEX when relative-strength research requires it.
- [x] 5.6 Attach row count and coverage metadata to `DatasetRef`.
- [x] 5.7 Attach data quality status to `DatasetRef`.
- [x] 5.8 Refuse or warn when dataset coverage is insufficient.

## 6. Output validation and caveats

- [x] 6.1 Add research artifact validator.
- [x] 6.2 Validate required `manifest.json`.
- [x] 6.3 Validate required `result.json`.
- [x] 6.4 Validate required `summary.md`.
- [x] 6.5 Validate lineage exists.
- [x] 6.6 Validate quality status exists.
- [x] 6.7 Validate caveats exist.
- [x] 6.8 Validate sample size and period coverage are present for experiments and hypothesis tests.
- [x] 6.9 Validate no personalized buy/sell recommendation appears in the final artifact.
- [x] 6.10 Add reusable caveat generator for sample size, data quality, lookahead bias, survivorship bias, transaction cost exclusion, and research-only status.

## 7. Indicator experiments

- [x] 7.1 Support indicator experiment definition from natural language or command text.
- [x] 7.2 Resolve input dataset snapshot.
- [x] 7.3 Generate or select calculation code/template.
- [x] 7.4 Execute through sandbox or approved deterministic tool.
- [x] 7.5 Validate output schema.
- [x] 7.6 Persist metrics and artifacts.
- [x] 7.7 Render summary with caveats.
- [x] 7.8 MVP supported indicator: relative strength over N sessions versus VNINDEX.

## 8. Feature engineering

- [x] 8.1 Support feature definition syntax.
- [x] 8.2 MVP supported feature expression: `feature_name = expression`.
- [x] 8.3 Persist feature metadata before full computation.
- [x] 8.4 Compute feature through sandbox or deterministic tool.
- [x] 8.5 Validate feature output completeness.
- [x] 8.6 Validate feature output date/symbol coverage.
- [x] 8.7 Attach lineage and quality status.
- [x] 8.8 Render feature validation result inline.
- [x] 8.9 Reject feature definitions that reference future data or execution actions.

## 9. Hypothesis tests

- [x] 9.1 Parse hypothesis text into sample, condition, outcome, horizon, and metric where possible.
- [x] 9.2 Require plan preview before execution.
- [x] 9.3 Execute bounded research computation.
- [x] 9.4 Produce sample size, period coverage, metric table, and caveats.
- [x] 9.5 Persist hypothesis test result.
- [x] 9.6 Render conclusion as evidence, not recommendation.
- [x] 9.7 If parsing is ambiguous, state assumptions in the plan preview.

## 10. Pattern scans

- [x] 10.1 Support pattern scan definitions such as accumulation base, volatility contraction, relative strength, and volume dry-up.
- [x] 10.2 Resolve symbol universe and date range.
- [x] 10.3 Execute scan through sandbox or deterministic tool.
- [x] 10.4 Persist candidate table and parameters.
- [x] 10.5 Attach data quality warnings.
- [x] 10.6 Render candidates as research outputs, not trading advice.
- [x] 10.7 MVP supported pattern: accumulation base + volatility contraction + volume dry-up.

## 11. Offline event studies

- [x] 11.1 Support event condition, horizon, exit condition, and metric definitions.
- [x] 11.2 Label workflow as offline research event study.
- [x] 11.3 Compute metrics without broker or live account state.
- [x] 11.4 Include transaction cost caveat if not modeled.
- [x] 11.5 Include lookahead bias and survivorship bias caveats.
- [x] 11.6 Persist event-study artifact.
- [x] 11.7 Refuse requests to execute, deploy, or automate live trades from event-study results.

## 12. Observability

- [x] 12.1 Emit `RESEARCH_ARTIFACT_CREATED`.
- [x] 12.2 Emit `RESEARCH_EXPERIMENT_CREATED`.
- [x] 12.3 Emit `RESEARCH_EXPERIMENT_SUCCEEDED`.
- [x] 12.4 Emit `RESEARCH_EXPERIMENT_FAILED`.
- [x] 12.5 Emit `RESEARCH_FEATURE_CREATED`.
- [x] 12.6 Emit `RESEARCH_FEATURE_VALIDATED`.
- [x] 12.7 Emit `RESEARCH_HYPOTHESIS_TESTED`.
- [x] 12.8 Emit `PATTERN_SCAN_COMPLETED`.
- [x] 12.9 Emit `OFFLINE_EVENT_STUDY_COMPLETED`.
- [x] 12.10 Link research automation events to sandbox job correlation IDs.
- [x] 12.11 Preserve redaction-by-default.

## 13. Tests

- [x] 13.1 Test `/experiment indicator` happy path.
- [x] 13.2 Test `/experiment backtest` labels output as research-only.
- [x] 13.3 Test `/feature create` persists feature metadata.
- [x] 13.4 Test `/feature validate` validates schema and coverage.
- [x] 13.5 Test `/hypothesis test` produces structured artifact.
- [x] 13.6 Test `/pattern scan` produces candidate artifact.
- [x] 13.7 Test live trading-like request is refused.
- [x] 13.8 Test every artifact includes lineage and caveats.
- [x] 13.9 Test generated code routes only through sandbox.
- [x] 13.10 Test no artifact contains personalized buy/sell recommendation text.
- [x] 13.11 Test insufficient dataset coverage creates warning or refusal.

## 14. Implementation slices

- [x] 14.1 Slice 1: models + artifact layout + validators.
- [x] 14.2 Slice 2: `/feature create` + `/feature validate`.
- [x] 14.3 Slice 3: `/experiment indicator`.
- [x] 14.4 Slice 4: `/pattern scan`.
- [x] 14.5 Slice 5: `/hypothesis test`.
- [x] 14.6 Slice 6: `/experiment backtest` as offline event study.
- [x] 14.7 Slice 7: assistant natural-language integration.

## 15. Documentation and validation

- [x] 15.1 Add research automation user guide.
- [x] 15.2 Document offline event study vs trading backtest boundary.
- [x] 15.3 Document common caveats.
- [x] 15.4 Document artifact layout.
- [x] 15.5 Document command examples.
- [x] 15.6 Run `make test-vnalpha`.
- [x] 15.7 Run `make lint-vnalpha`.
- [x] 15.8 Run `make verify-r4`.
- [x] 15.9 Run `openstock-verify --ci`.
- [x] 15.10 Run `pytest vnalpha/tests -k "experiment or feature or hypothesis or pattern or research_automation"`.
- [x] 15.11 Attach validation evidence to PR.
