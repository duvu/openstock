## 1. Deterministic answer boundary

- [x] 1.1 Add a generic validated deterministic answer path for successful read-only tool output.
- [x] 1.2 Preserve fail-closed behavior for unsafe execution, failed tools, and missing evidence.

## 2. Degraded lifecycle

- [x] 2.1 Add finite downstream stage/category metadata and `DEGRADED_SUCCESS` behavior.
- [x] 2.2 Isolate synthesis, audit, projection, and finalization failures after an answer exists.
- [x] 2.3 Persist sanitized correlation, build, model-route, and trace evidence where available.

## 3. Shared presentation

- [x] 3.1 Render bounded degraded diagnostics through CLI and TUI without raw exception leakage.
- [x] 3.2 Keep managed and connected execution on the shared contract.

## 4. Contract evidence

- [x] 4.1 Extend the owning assistant contract test with downstream degradation cases and one planner-to-tool-to-fallback observable path.
- [x] 4.2 Run the focused owning contract test through `make test-loop` and record exact evidence.
- [ ] 4.3 Run required repository gates once at final PR lifecycle stage and update closure evidence.
