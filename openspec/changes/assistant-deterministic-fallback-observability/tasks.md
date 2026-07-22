## 1. Deterministic answer boundary

- [ ] 1.1 Identify the shared read-only tool-output renderer and add a generic validated deterministic answer path.
- [ ] 1.2 Preserve fail-closed behavior for unsafe execution, failed tools, and missing deterministic evidence.

## 2. Degraded lifecycle

- [ ] 2.1 Add finite downstream stage/category metadata and `DEGRADED_SUCCESS` answer/session behavior.
- [ ] 2.2 Isolate synthesis, audit, projection, and session-finalization failures after an answer exists.
- [ ] 2.3 Persist sanitized correlation, build, model-route, and trace evidence where available.

## 3. Shared presentation

- [ ] 3.1 Render the bounded degraded diagnostic contract through CLI and TUI without raw exception leakage.
- [ ] 3.2 Keep connected and managed execution paths on the shared contract.

## 4. Contract evidence

- [ ] 4.1 Extend the owning assistant contract test with gateway, parser, validation, audit, projection, and finalization degradation cases plus one planner-to-tool-to-fallback observable path.
- [ ] 4.2 Run the focused owning contract test through `make test-loop` and record exact evidence in this change.
- [ ] 4.3 Run required repository gates once at final PR lifecycle stage and update issue/OpenSpec closure evidence.
