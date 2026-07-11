# Tasks: Deep Symbol Analysis Engine

## 0. Governance

- [x] 0.1 Keep outputs research-only.
- [x] 0.2 Do not produce buy/sell/order/allocation/account/broker/margin instructions.
- [x] 0.3 Include caveats and missing-data disclosure.

## 1. Models and persistence

- [x] 1.1 Reuse or add `SetupAnalysis` persistence.
- [x] 1.2 Reuse or add `SymbolLevelSnapshot` persistence.
- [x] 1.3 Add `DeepSymbolAnalysis` contract.
- [x] 1.4 Persist analysis artifact references.

## 2. Builders

- [x] 2.1 Add `DeepAnalysisBuilder`.
- [x] 2.2 Add `LevelExtractor`.
- [x] 2.3 Add `SetupQualityEvaluator`.
- [x] 2.4 Add `ConfidenceEvaluator`.
- [x] 2.5 Add context assembler.

## 3. Feature/context blocks

- [x] 3.1 Build trend context.
- [x] 3.2 Build momentum context.
- [x] 3.3 Build relative strength context.
- [x] 3.4 Build volume context.
- [x] 3.5 Build volatility context.
- [x] 3.6 Build support/resistance context.
- [x] 3.7 Build setup quality context.
- [x] 3.8 Build caveated scenario summary.

## 4. Commands and tools

- [x] 4.1 Add `/analyze SYMBOL`.
- [x] 4.2 Add `analysis.deep_symbol` tool.
- [x] 4.3 Add assistant intent `deep_analyze_symbol`.
- [x] 4.4 Add synthesis template.
- [x] 4.5 Add help/docs examples.

## 5. Tests

- [x] 5.1 Test analysis output contains all required blocks.
- [x] 5.2 Test missing data caveats.
- [x] 5.3 Test level extraction output.
- [x] 5.4 Test setup quality decomposition.
- [x] 5.5 Test assistant route.
- [x] 5.6 Test no trading/execution language.

## 6. Validation

- [x] 6.1 Run `make test-vnalpha`.
- [x] 6.2 Run `make lint-vnalpha`.
- [x] 6.3 Run `make verify-r4`.
- [x] 6.4 Run `openstock-verify --ci`.
