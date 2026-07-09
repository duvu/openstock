# Tasks: Research automation for opencode-like auto research

## 0. Governance

- [ ] 0.1 Keep all research automation inside the read-only research boundary.
- [ ] 0.2 Do not introduce broker, order, account, portfolio, margin, transfer, allocation, or trading execution tools.
- [ ] 0.3 Label offline backtest-like workflows as research event studies, not live trading workflows.
- [ ] 0.4 Preserve redaction-by-default logging.
- [ ] 0.5 Persist lineage and reproducibility evidence for every research artifact.
- [ ] 0.6 Do not present research output as personalized financial advice.

## 1. Research automation models

- [ ] 1.1 Add `ResearchExperiment` model or equivalent.
- [ ] 1.2 Add `ResearchFeature` model or equivalent.
- [ ] 1.3 Add `ResearchHypothesis` model or equivalent.
- [ ] 1.4 Add `PatternScan` model or equivalent.
- [ ] 1.5 Add `OfflineEventStudy` model or equivalent.
- [ ] 1.6 Add `ResearchArtifact` model or equivalent.
- [ ] 1.7 Add lineage, quality status, dataset references, and correlation ID fields.

## 2. Persistence and artifact layout

- [ ] 2.1 Add warehouse migrations for research automation metadata if database-backed.
- [ ] 2.2 Persist experiment definitions.
- [ ] 2.3 Persist feature definitions.
- [ ] 2.4 Persist hypothesis definitions.
- [ ] 2.5 Persist pattern scan definitions.
- [ ] 2.6 Persist event-study definitions.
- [ ] 2.7 Persist result artifacts under run/job artifact folders.
- [ ] 2.8 Persist reproducibility manifest.

## 3. Command surface

- [ ] 3.1 Add `/experiment indicator <description>`.
- [ ] 3.2 Add `/experiment backtest <event-study-description>` and document that it means offline research event study.
- [ ] 3.3 Add `/feature create <definition>`.
- [ ] 3.4 Add `/feature validate <feature-id-or-name>`.
- [ ] 3.5 Add `/hypothesis test <hypothesis-text>`.
- [ ] 3.6 Add `/pattern scan <pattern-description>`.
- [ ] 3.7 Render unsupported subcommands inline.
- [ ] 3.8 Emit command lifecycle events for every research automation command.

## 4. Assistant planning

- [ ] 4.1 Extend intent classification for indicator experiment requests.
- [ ] 4.2 Extend intent classification for feature creation/validation requests.
- [ ] 4.3 Extend intent classification for hypothesis test requests.
- [ ] 4.4 Extend intent classification for pattern scan requests.
- [ ] 4.5 Extend intent classification for offline event-study requests.
- [ ] 4.6 Build deterministic plan templates for each supported research automation type.
- [ ] 4.7 Require sandbox approval when generated code execution is needed.
- [ ] 4.8 Refuse or mark unsupported requests that imply live trading or execution.

## 5. Indicator experiments

- [ ] 5.1 Support indicator experiment definition from natural language or command text.
- [ ] 5.2 Resolve input dataset snapshot.
- [ ] 5.3 Generate or select calculation code/template.
- [ ] 5.4 Execute through sandbox or approved deterministic tool.
- [ ] 5.5 Validate output schema.
- [ ] 5.6 Persist metrics and artifacts.
- [ ] 5.7 Render summary with caveats.

## 6. Feature engineering

- [ ] 6.1 Support feature definition syntax.
- [ ] 6.2 Persist feature metadata.
- [ ] 6.3 Compute feature through sandbox or deterministic tool.
- [ ] 6.4 Validate feature output completeness.
- [ ] 6.5 Validate feature output date/symbol coverage.
- [ ] 6.6 Attach lineage and quality status.
- [ ] 6.7 Render feature validation result inline.

## 7. Hypothesis tests

- [ ] 7.1 Parse hypothesis text into sample, condition, outcome, horizon, and metric where possible.
- [ ] 7.2 Require plan preview before execution.
- [ ] 7.3 Execute bounded research computation.
- [ ] 7.4 Produce sample size, period coverage, metric table, and caveats.
- [ ] 7.5 Persist hypothesis test result.
- [ ] 7.6 Render conclusion as evidence, not recommendation.

## 8. Pattern scans

- [ ] 8.1 Support pattern scan definitions such as accumulation base, volatility contraction, relative strength, and volume breakout.
- [ ] 8.2 Resolve symbol universe and date range.
- [ ] 8.3 Execute scan through sandbox or deterministic tool.
- [ ] 8.4 Persist candidate table and parameters.
- [ ] 8.5 Attach data quality warnings.
- [ ] 8.6 Render candidates as research outputs, not trading advice.

## 9. Offline event studies

- [ ] 9.1 Support event condition, horizon, exit condition, and metric definitions.
- [ ] 9.2 Label workflow as offline research event study.
- [ ] 9.3 Compute metrics without broker or live account state.
- [ ] 9.4 Include transaction cost caveat if not modeled.
- [ ] 9.5 Include lookahead bias and survivorship bias caveats.
- [ ] 9.6 Persist event-study artifact.

## 10. Observability

- [ ] 10.1 Emit `RESEARCH_EXPERIMENT_CREATED`.
- [ ] 10.2 Emit `RESEARCH_EXPERIMENT_SUCCEEDED`.
- [ ] 10.3 Emit `RESEARCH_EXPERIMENT_FAILED`.
- [ ] 10.4 Emit `RESEARCH_FEATURE_CREATED`.
- [ ] 10.5 Emit `RESEARCH_HYPOTHESIS_TESTED`.
- [ ] 10.6 Emit `PATTERN_SCAN_COMPLETED`.
- [ ] 10.7 Link research automation events to sandbox job correlation IDs.
- [ ] 10.8 Preserve redaction-by-default.

## 11. Tests

- [ ] 11.1 Test `/experiment indicator` happy path.
- [ ] 11.2 Test `/experiment backtest` labels output as research-only.
- [ ] 11.3 Test `/feature create` persists feature metadata.
- [ ] 11.4 Test `/feature validate` validates schema and coverage.
- [ ] 11.5 Test `/hypothesis test` produces structured artifact.
- [ ] 11.6 Test `/pattern scan` produces candidate artifact.
- [ ] 11.7 Test live trading-like request is refused.
- [ ] 11.8 Test every artifact includes lineage and caveats.

## 12. Documentation and validation

- [ ] 12.1 Add research automation user guide.
- [ ] 12.2 Document offline event study vs trading backtest boundary.
- [ ] 12.3 Document common caveats.
- [ ] 12.4 Run `make test-vnalpha`.
- [ ] 12.5 Run `make lint-vnalpha`.
- [ ] 12.6 Run `make verify-r4`.
- [ ] 12.7 Run `openstock-verify --ci`.
- [ ] 12.8 Attach validation evidence to PR.
