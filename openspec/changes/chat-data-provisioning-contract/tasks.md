# Tasks: chat data provisioning contract (issues #163 and #175)

- [x] 1. Add `force_refresh` to the data-availability ensure engine and legacy wrapper.
- [x] 2. Add `ensure_current_symbol_ready` typed operation and `CurrentSymbolReadyResult`.
- [x] 3. Export the operation from `vnalpha.data_provisioning`.
- [x] 4. Add the `data.ensure_current_symbol` tool capability, implementation and registration.
- [x] 5. Replace the `fetch_data` refusal with an explicit provisioning step.
- [x] 6. Prepend the explicit provisioning step to the deep-analysis plan.
- [x] 7. Remove the hidden executor pre-step when a plan provisions explicitly; thread one correlation ID; fail closed on non-ready provisioning.
- [x] 8. Exclude the provisioning tool from the groundedness claim/field contract.
- [x] 9. Route `/analyze` through the shared operation.
- [x] 10. Add focused tests (empty warehouse, fresh reuse, explicit refresh, partial failure, service unavailable, planner/executor trace, fail-closed, policy eligibility).
- [x] 11. Update `docs/data-provisioning-commands.md`.
- [x] 12. Record merged CI evidence for PR #168 and current focused regressions in `validation.md`.
- [x] 13. Parse nullable, malformed, duplicate, empty, and oversized remediation payloads without crashing or emitting unbounded CLI/TUI content.
