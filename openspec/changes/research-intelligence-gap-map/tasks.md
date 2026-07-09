# Tasks: Research intelligence gap map

## 0. Governance

- [x] 0.1 Treat this as a planning/gap-assessment change only.
- [x] 0.2 Do not implement runtime engines in this change.
- [x] 0.3 Do not mark future implementation tasks complete.
- [x] 0.4 Keep outputs research-only.
- [x] 0.5 Preserve existing safety and policy boundaries.
- [x] 0.6 Avoid wording that implies certainty or personalised instruction.

## 1. Gap map document

- [x] 1.1 Add `vnalpha/docs/research-intelligence-gap-map.md`.
- [x] 1.2 Document current capability inventory.
- [x] 1.3 Document target capability model.
- [x] 1.4 Add formal gap matrix.
- [x] 1.5 Add prioritised roadmap.
- [x] 1.6 Add future OpenSpec split.
- [x] 1.7 Add policy guardrail section.
- [x] 1.8 Add evaluation/golden-set section.

## 2. Current capability inventory

- [x] 2.1 Inventory data ingestion capabilities.
- [x] 2.2 Inventory warehouse artifacts.
- [x] 2.3 Inventory current feature coverage.
- [x] 2.4 Inventory current scoring model.
- [x] 2.5 Inventory watchlist generation.
- [x] 2.6 Inventory command handlers.
- [x] 2.7 Inventory assistant intents and tools.
- [x] 2.8 Inventory TUI support.
- [x] 2.9 Inventory observability support.
- [x] 2.10 Inventory tests/evaluation assets.

## 3. Target capability definitions

- [x] 3.1 Define deep symbol analysis target output.
- [x] 3.2 Define market regime target output.
- [x] 3.3 Define sector context target output.
- [x] 3.4 Define watchlist synthesis target output.
- [x] 3.5 Define shortlist generation target output.
- [x] 3.6 Define conditional research scenario target output.
- [x] 3.7 Define historical evidence target output.
- [x] 3.8 Define assistant workflow target output.
- [x] 3.9 Define TUI workflow target output.

## 4. Gap matrix

- [x] 4.1 Add gap row for deep symbol analysis.
- [x] 4.2 Add gap row for multi-timeframe features.
- [x] 4.3 Add gap row for support/resistance levels.
- [x] 4.4 Add gap row for setup quality model.
- [x] 4.5 Add gap row for risk/reward estimate.
- [x] 4.6 Add gap row for market regime.
- [x] 4.7 Add gap row for sector strength.
- [x] 4.8 Add gap row for watchlist synthesis.
- [x] 4.9 Add gap row for shortlist generation.
- [x] 4.10 Add gap row for conditional research scenario planning.
- [x] 4.11 Add gap row for historical evidence.
- [x] 4.12 Add gap row for assistant intents/tools.
- [x] 4.13 Add gap row for TUI research workflow.
- [x] 4.14 Add gap row for observability.
- [x] 4.15 Add gap row for evaluation/golden sets.
- [x] 4.16 Add gap row for policy guardrails.

## 5. Data and schema gaps

- [x] 5.1 Identify need for market regime snapshots.
- [x] 5.2 Identify need for sector strength snapshots.
- [x] 5.3 Identify need for symbol level snapshots.
- [x] 5.4 Identify need for setup analysis records.
- [x] 5.5 Identify need for shortlist candidate records.
- [x] 5.6 Identify need for research scenario plan records.
- [x] 5.7 Identify need for setup historical evidence records.
- [x] 5.8 Identify need for research answer audit records.

## 6. Feature engineering gaps

- [x] 6.1 Identify weekly/multi-timeframe features.
- [x] 6.2 Identify momentum window gaps.
- [x] 6.3 Identify drawdown/extendedness gaps.
- [x] 6.4 Identify base duration and base quality gaps.
- [x] 6.5 Identify support/resistance level gaps.
- [x] 6.6 Identify breadth feature gaps.
- [x] 6.7 Identify sector-relative feature gaps.
- [x] 6.8 Identify setup outcome feature gaps.

## 7. Command/API gaps

- [x] 7.1 Define `/analyze SYMBOL` gap.
- [x] 7.2 Define `/market-regime` gap.
- [x] 7.3 Define `/sector-strength` gap.
- [x] 7.4 Define `/watchlist-summary` gap.
- [x] 7.5 Define `/shortlist` gap.
- [x] 7.6 Define `/research-plan SYMBOL` gap.
- [x] 7.7 Define `/setup-evidence` gap.
- [x] 7.8 Define API/tool output contracts for each command.

## 8. Assistant gaps

- [x] 8.1 Define `deep_analyze_symbol` intent gap.
- [x] 8.2 Define `review_market_regime` intent gap.
- [x] 8.3 Define `review_sector_strength` intent gap.
- [x] 8.4 Define `summarize_watchlist_deep` intent gap.
- [x] 8.5 Define `generate_shortlist` intent gap.
- [x] 8.6 Define `generate_research_scenario` intent gap.
- [x] 8.7 Define `review_setup_evidence` intent gap.
- [x] 8.8 Define required tools for each intent.
- [x] 8.9 Define synthesis template gaps.
- [x] 8.10 Define groundedness requirements.

## 9. TUI gaps

- [x] 9.1 Define deep analysis rendering gaps.
- [x] 9.2 Define shortlist rendering gaps.
- [x] 9.3 Define scenario plan rendering gaps.
- [x] 9.4 Define historical evidence rendering gaps.
- [x] 9.5 Define status/progress gaps for long workflows.
- [x] 9.6 Define keyboard workflow gaps.

## 10. Observability and evaluation gaps

- [x] 10.1 Define events needed for deep analysis.
- [x] 10.2 Define events needed for shortlist generation.
- [x] 10.3 Define events needed for scenario planning.
- [x] 10.4 Define events needed for historical evidence.
- [x] 10.5 Define golden-set files.
- [x] 10.6 Define groundedness checks.
- [x] 10.7 Define policy-safety checks.
- [x] 10.8 Define scenario quality checks.

## 11. Future OpenSpec split

- [x] 11.1 Define `deep-symbol-analysis-engine` OpenSpec scope.
- [x] 11.2 Define `market-regime-and-sector-context` OpenSpec scope.
- [x] 11.3 Define `watchlist-synthesis-and-shortlist` OpenSpec scope.
- [x] 11.4 Define `research-scenario-plan-engine` OpenSpec scope.
- [x] 11.5 Define `setup-historical-evidence-engine` OpenSpec scope.
- [x] 11.6 Define `assistant-research-intelligence-tools` OpenSpec scope.
- [x] 11.7 Define `tui-research-workflow-polish` OpenSpec scope.

## 12. Validation

- [x] 12.1 Confirm gap map doc exists.
- [x] 12.2 Confirm all major capabilities have current/target/gap/priority rows.
- [x] 12.3 Confirm future OpenSpec split is clear.
- [x] 12.4 Confirm policy constraints are explicit.
- [x] 12.5 Confirm no runtime work is claimed complete.

