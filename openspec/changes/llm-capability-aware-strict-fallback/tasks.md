## 1. Routing contract

- [x] 1.1 Populate route decisions with explicitly configured capabilities.
- [x] 1.2 Add optional required-capability filtering to fallback resolution.
- [x] 1.3 Preserve configured order and duplicate-model suppression.

## 2. Gateway behavior

- [x] 2.1 Use verified `json_schema` fallbacks after strict primary failure.
- [x] 2.2 Add typed `no_compatible_fallback` error with primary cause.
- [x] 2.3 Preserve non-strict fallback and one-downgrade-per-route behavior.

## 3. Operator surfaces and documentation

- [x] 3.1 Expose capabilities and strict-schema fallbacks in `/model` surfaces.
- [x] 3.2 Update environment/package templates and AI-layer documentation.
- [x] 3.3 Add focused tests to required CI.

## 4. Validation

- [x] 4.1 Add focused routing, gateway, error and status tests.
- [ ] 4.2 Run repository consistency, Ruff, R0, full suite and package build on the final PR SHA.
