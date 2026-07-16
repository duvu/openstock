# Tasks: chat data provisioning contract (issue #163)

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
- [ ] 12. Record final CI evidence on the merge SHA in `validation.md` (pending PR).
