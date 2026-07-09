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

## 5. Tests

- [ ] 5.1 Test analysis output contains all required blocks.
- [ ] 5.2 Test missing data caveats.
- [ ] 5.3 Test level extraction output.
- [ ] 5.4 Test setup quality decomposition.
- [ ] 5.5 Test assistant route.
- [ ] 5.6 Test no trading/execution language.

## 6. Validation

- [ ] 6.1 Run `make test-vnalpha`.
- [ ] 6.2 Run `make lint-vnalpha`.
- [ ] 6.3 Run `make verify-r4`.
- [ ] 6.4 Run `openstock-verify --ci`.
