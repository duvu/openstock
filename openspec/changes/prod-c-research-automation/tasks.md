# Tasks: Research automation for opencode-like auto research

## 0. Governance

- [ ] 0.1 Keep all research automation inside the no-trading-execution boundary.
- [ ] 0.2 Do not introduce broker, order, account, portfolio, margin, transfer, allocation, or trading execution tools.
- [ ] 0.3 Label offline backtest-like workflows as offline research event studies, not live trading workflows.
- [ ] 0.4 Preserve redaction-by-default logging.
- [ ] 0.5 Persist lineage and reproducibility evidence for every research artifact.
- [ ] 0.6 Do not present research output as personalized financial advice.
- [ ] 0.7 Require sandbox execution for generated research code.
- [ ] 0.8 Require explicit approval before executing generated sandbox code.
- [ ] 0.9 Do not implement all research automation commands in one large PR; use implementation slices.

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

- [ ] 3.1 Add `/experiment indicator <description> [--universe UNIVERSE] [--start YYYY-MM-DD] [--end YYYY-MM-DD]`.
- [ ] 3.2 Add `/experiment backtest <event-study-description> [--horizon N] [--start YYYY-MM-DD] [--end YYYY-MM-DD]` and render it as an offline research event study.
- [ ] 3.3 Add `/feature create <definition>`.
- [ ] 3.4 Add `/feature validate <feature-id-or-name>`.
- [ ] 3.5 Add `/hypothesis test <hypothesis-text>`.
- [ ] 3.6 Add `/pattern scan <pattern-description> [--universe UNIVERSE] [--date YYYY-MM-DD]`.
- [ ] 3.7 Render unsupported subcommands inline.
- [ ] 3.8 Emit command lifecycle events for every research automation command.
- [ ] 3.9 Add command help output for all research automation commands.
- [ ] 3.10 Ensure command examples use Vietnamese equity symbols/universes, not US examples.

## 4. Assistant planning

- [ ] 4.1 Extend intent classification for `create_indicator_experiment`.
- [ ] 4.2 Extend intent classification for `create_feature`.
- [ ] 4.3 Extend intent classification for `validate_feature`.
- [ ] 4.4 Extend intent classification for `test_hypothesis`.
- [ ] 4.5 Extend intent classification for `scan_pattern`.
- [ ] 4.6 Extend intent classification for `run_offline_event_study`.
- [ ] 4.7 Build deterministic plan templates for each supported research automation intent.
- [ ] 4.8 Resolve dataset snapshot and universe before computation.
- [ ] 4.9 Require sandbox approval when generated code execution is needed.
- [ ] 4.10 Refuse or mark unsupported requests that imply live trading or execution.
- [ ] 4.11 Add plan preview that shows dataset refs, generated-code summary, expected artifacts, and caveats.

## 5. Dataset resolution

- [ ] 5.1 Add `DatasetResolver` or equivalent.
- [ ] 5.2 Resolve symbol universe.
- [ ] 5.3 Resolve date range.
- [ ] 5.4 Resolve interval.
- [ ] 5.5 Resolve benchmark index such as VNINDEX when relative-strength research requires it.
- [ ] 5.6 Attach row count and coverage metadata to `DatasetRef`.
- [ ] 5.7 Attach data quality status to `DatasetRef`.
- [ ] 5.8 Refuse or warn when dataset coverage is insufficient.

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

- [ ] 7.1 Support indicator experiment definition from natural language or command text.
- [ ] 7.2 Resolve input dataset snapshot.
- [ ] 7.3 Generate or select calculation code/template.
- [ ] 7.4 Execute through sandbox or approved deterministic tool.
- [ ] 7.5 Validate output schema.
- [ ] 7.6 Persist metrics and artifacts.
- [ ] 7.7 Render summary with caveats.
- [ ] 7.8 MVP supported indicator: relative strength over N sessions versus VNINDEX.

## 8. Feature engineering

- [ ] 8.1 Support feature definition syntax.
- [ ] 8.2 MVP supported feature expression: `feature_name = expression`.
- [ ] 8.3 Persist feature metadata before full computation.
- [ ] 8.4 Compute feature through sandbox or deterministic tool.
- [ ] 8.5 Validate feature output completeness.
- [ ] 8.6 Validate feature output date/symbol coverage.
- [ ] 8.7 Attach lineage and quality status.
- [ ] 8.8 Render feature validation result inline.
- [ ] 8.9 Reject feature definitions that reference future data or execution actions.

## 9. Hypothesis tests

- [ ] 9.1 Parse hypothesis text into sample, condition, outcome, horizon, and metric where possible.
- [ ] 9.2 Require plan preview before execution.
- [ ] 9.3 Execute bounded research computation.
- [ ] 9.4 Produce sample size, period coverage, metric table, and caveats.
- [ ] 9.5 Persist hypothesis test result.
- [ ] 9.6 Render conclusion as evidence, not recommendation.
- [ ] 9.7 If parsing is ambiguous, state assumptions in the plan preview.

## 10. Pattern scans

- [ ] 10.1 Support pattern scan definitions such as accumulation base, volatility contraction, relative strength, and volume dry-up.
- [ ] 10.2 Resolve symbol universe and date range.
- [ ] 10.3 Execute scan through sandbox or deterministic tool.
- [ ] 10.4 Persist candidate table and parameters.
- [ ] 10.5 Attach data quality warnings.
- [ ] 10.6 Render candidates as research outputs, not trading advice.
- [ ] 10.7 MVP supported pattern: accumulation base + volatility contraction + volume dry-up.

## 11. Offline event studies

- [ ] 11.1 Support event condition, horizon, exit condition, and metric definitions.
- [ ] 11.2 Label workflow as offline research event study.
- [ ] 11.3 Compute metrics without broker or live account state.
- [ ] 11.4 Include transaction cost caveat if not modeled.
- [ ] 11.5 Include lookahead bias and survivorship bias caveats.
- [ ] 11.6 Persist event-study artifact.
- [ ] 11.7 Refuse requests to execute, deploy, or automate live trades from event-study results.

## 12. Observability

- [ ] 12.1 Emit `RESEARCH_ARTIFACT_CREATED`.
- [ ] 12.2 Emit `RESEARCH_EXPERIMENT_CREATED`.
- [ ] 12.3 Emit `RESEARCH_EXPERIMENT_SUCCEEDED`.
- [ ] 12.4 Emit `RESEARCH_EXPERIMENT_FAILED`.
- [ ] 12.5 Emit `RESEARCH_FEATURE_CREATED`.
- [ ] 12.6 Emit `RESEARCH_FEATURE_VALIDATED`.
- [ ] 12.7 Emit `RESEARCH_HYPOTHESIS_TESTED`.
- [ ] 12.8 Emit `PATTERN_SCAN_COMPLETED`.
- [ ] 12.9 Emit `OFFLINE_EVENT_STUDY_COMPLETED`.
- [ ] 12.10 Link research automation events to sandbox job correlation IDs.
- [ ] 12.11 Preserve redaction-by-default.

## 13. Tests

- [ ] 13.1 Test `/experiment indicator` happy path.
- [ ] 13.2 Test `/experiment backtest` labels output as research-only.
- [ ] 13.3 Test `/feature create` persists feature metadata.
- [ ] 13.4 Test `/feature validate` validates schema and coverage.
- [ ] 13.5 Test `/hypothesis test` produces structured artifact.
- [ ] 13.6 Test `/pattern scan` produces candidate artifact.
- [ ] 13.7 Test live trading-like request is refused.
- [ ] 13.8 Test every artifact includes lineage and caveats.
- [ ] 13.9 Test generated code routes only through sandbox.
- [ ] 13.10 Test no artifact contains personalized buy/sell recommendation text.
- [ ] 13.11 Test insufficient dataset coverage creates warning or refusal.

## 14. Implementation slices

- [x] 14.1 Slice 1: models + artifact layout + validators.
- [ ] 14.2 Slice 2: `/feature create` + `/feature validate`.
- [ ] 14.3 Slice 3: `/experiment indicator`.
- [ ] 14.4 Slice 4: `/pattern scan`.
- [ ] 14.5 Slice 5: `/hypothesis test`.
- [ ] 14.6 Slice 6: `/experiment backtest` as offline event study.
- [ ] 14.7 Slice 7: assistant natural-language integration.

## 15. Documentation and validation

- [ ] 15.1 Add research automation user guide.
- [ ] 15.2 Document offline event study vs trading backtest boundary.
- [ ] 15.3 Document common caveats.
- [ ] 15.4 Document artifact layout.
- [ ] 15.5 Document command examples.
- [ ] 15.6 Run `make test-vnalpha`.
- [ ] 15.7 Run `make lint-vnalpha`.
- [ ] 15.8 Run `make verify-r4`.
- [ ] 15.9 Run `openstock-verify --ci`.
- [ ] 15.10 Run `pytest vnalpha/tests -k "experiment or feature or hypothesis or pattern or research_automation"`.
- [ ] 15.11 Attach validation evidence to PR.
