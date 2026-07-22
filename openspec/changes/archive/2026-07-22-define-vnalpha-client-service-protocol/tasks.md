## 1. Contract discovery and ownership

- [x] 1.1 Review #376 and #317, #322, #325, #326, #337, #339, #343 and #344; record the client/service boundary without duplicating their owned queue, readiness, worker or maintenance policies. Evidence: issue contracts and the active queue OpenSpec were reviewed before the v1 boundary was written.
- [x] 1.2 Define the production ownership model for the client, control service, worker, timers and `vnstock-service`, including the direct-access prohibitions and limited in-process exception. Evidence: proposal, design decision 1/8 and the ownership/direct-access requirements.

## 2. Versioned local protocol

- [x] 2.1 Define the finite v1 public operation enum and classify each initial operation as a synchronous query, immediate application command or durable job command. Evidence: design decision 3 and the finite-operation requirement enumerate every #377 operation.
- [x] 2.2 Define typed request, response, error and metadata envelopes that preserve result status, effective date/capability, freshness, lineage, limitations, durable identity and correlation. Evidence: design decisions 2/5 and the envelope/evidence requirements.
- [x] 2.3 Define the `READY|DEGRADED|ACCEPTED|PENDING|BUSY|UNAVAILABLE|FAILED` result meanings and the inherited non-cancelling wait/disconnect behavior. Evidence: design decisions 4/7 and the result/durable-observation requirements.
- [x] 2.4 Define UDS path, ownership, permissions, framing, compatibility and fail-closed actionable error behavior. Evidence: design decisions 2/6 and the transport/compatibility/error requirements.

## 3. Completion evidence

- [x] 3.1 Review the proposal, design and specification against every #377 acceptance criterion and the linked issue contracts. Evidence: requirement audit and linked queue-contract search completed before strict validation.
- [x] 3.2 Run OpenSpec validation/status checks and record that #377 is specification-only with no runtime implementation or test contract required. Evidence: `openspec validate define-vnalpha-client-service-protocol --strict` passed; issue #377 expressly requires no runtime implementation.
- [x] 3.3 Archive the completed specification change into the accepted OpenSpec capability and remove it from the active-change registry. Evidence: `openspec/specs/vnalpha-local-service-protocol/spec.md` is byte-identical to the validated delta; the change is archived at `2026-07-22-define-vnalpha-client-service-protocol`.
