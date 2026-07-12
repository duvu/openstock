# Tasks: Closed-loop repair and validation for auto research

## 0. Governance

- [x] 0.1 Keep the system inside the read-only research boundary.
- [x] 0.2 Do not introduce broker, order, account, portfolio, margin, transfer, allocation, or trading execution capabilities.
- [x] 0.3 Treat `/deploy` as research artifact promotion/rollback only.
- [x] 0.4 Preserve redaction-by-default logging.
- [x] 0.5 Preserve validation evidence before promotion.
- [x] 0.6 Bound all auto-repair loops with max attempts and terminal failure state.

## 1. Closed-loop lifecycle

- [x] 1.1 Define canonical states: `RUN`, `OBSERVE`, `PACKAGE`, `AI_FIX`, `VALIDATE`, `PROMOTE_READY`, `PROMOTED`, `REJECTED`, `ROLLED_BACK`, `FAILED`.
- [x] 1.2 Add lifecycle state persistence.
- [x] 1.3 Link lifecycle state to correlation ID.
- [x] 1.4 Link lifecycle state to sandbox job / research experiment / feature / hypothesis / pattern artifact IDs.
- [x] 1.5 Add terminal failure handling.

## 2. Repair bundle

- [x] 2.1 Add `RepairBundle` model or equivalent.
- [x] 2.2 Include repair ID.
- [x] 2.3 Include correlation ID.
- [x] 2.4 Include failed job/session ID.
- [x] 2.5 Include user request and plan summary.
- [x] 2.6 Include generated code.
- [x] 2.7 Include static guard result.
- [x] 2.8 Include stdout/stderr.
- [x] 2.9 Include error trace.
- [x] 2.10 Include input dataset references.
- [x] 2.11 Include artifact manifest/output state.
- [x] 2.12 Include validation result.
- [x] 2.13 Include environment summary.
- [x] 2.14 Include redaction status.

## 3. Repair commands

- [x] 3.1 Implement or bridge `/repair prepare --latest`.
- [x] 3.2 Implement or bridge `/repair prepare <job-id>`.
- [x] 3.3 Implement or bridge `/repair status <repair-id>`.
- [x] 3.4 Implement or bridge `/repair propose <repair-id>`.
- [x] 3.5 Implement or bridge `/repair apply <repair-id> --attempt <n>` for sandbox research artifacts only.
- [x] 3.6 Render unsupported repair subcommands inline.
- [x] 3.7 Emit command lifecycle events.

## 4. AI repair proposal

- [x] 4.1 Generate repair proposal from repair bundle.
- [x] 4.2 Limit repair proposal scope to sandbox research code, experiment definitions, feature definitions, or validation schemas.
- [x] 4.3 Include explanation of the suspected failure cause.
- [x] 4.4 Include proposed patch/diff or replacement generated code.
- [x] 4.5 Include expected validation checks.
- [x] 4.6 Reject repair proposals that include broker/order/account/portfolio/margin/trading execution behavior.

## 5. Bounded repair loop

- [x] 5.1 Add max repair attempts configuration.
- [x] 5.2 Re-run repaired job only inside sandbox.
- [x] 5.3 Persist every repair attempt.
- [x] 5.4 Capture stdout/stderr/error for every attempt.
- [x] 5.5 Stop after max attempts.
- [x] 5.6 Mark repair as failed when attempts are exhausted.

## 6. Validation gate

- [x] 6.1 Add `/validate run <artifact-id>`.
- [x] 6.2 Validate static guard pass.
- [x] 6.3 Validate sandbox execution pass.
- [x] 6.4 Validate output schema pass.
- [x] 6.5 Validate artifact manifest pass.
- [x] 6.6 Validate lineage present.
- [x] 6.7 Validate quality status present.
- [x] 6.8 Validate caveats present.
- [x] 6.9 Validate read-only boundary pass.
- [x] 6.10 Persist validation report.

## 7. Research artifact promotion

- [x] 7.1 Define promotable research artifact types.
- [x] 7.2 Add `/deploy verify <candidate>` for research artifact readiness.
- [x] 7.3 Add `/deploy promote <candidate> --deployment-id <id>` for research artifact promotion only.
- [x] 7.4 Add `/deploy rollback <deployment-id>` for research artifact rollback only.
- [x] 7.5 Persist deploy log.
- [x] 7.6 Prevent promotion if validation gate fails.
- [x] 7.7 Prevent promotion if read-only boundary check fails.

## 8. Observability

- [x] 8.1 Emit `REPAIR_BUNDLE_CREATED`.
- [x] 8.2 Emit `REPAIR_PROPOSAL_CREATED`.
- [x] 8.3 Emit `REPAIR_ATTEMPT_STARTED`.
- [x] 8.4 Emit `REPAIR_ATTEMPT_SUCCEEDED`.
- [x] 8.5 Emit `REPAIR_ATTEMPT_FAILED`.
- [x] 8.6 Emit `VALIDATION_STARTED`.
- [x] 8.7 Emit `VALIDATION_SUCCEEDED`.
- [x] 8.8 Emit `VALIDATION_FAILED`.
- [x] 8.9 Emit `RESEARCH_ARTIFACT_PROMOTED`.
- [x] 8.10 Emit `RESEARCH_ARTIFACT_ROLLED_BACK`.
- [x] 8.11 Link all events by correlation ID.
- [x] 8.12 Preserve redaction-by-default.

## 9. Tests

- [x] 9.1 Test `/repair prepare --latest` packages latest failure.
- [x] 9.2 Test repair bundle contains required sections.
- [x] 9.3 Test repair proposal rejects trading-execution content.
- [x] 9.4 Test repair loop stops at max attempts.
- [x] 9.5 Test repaired job reruns only inside sandbox.
- [x] 9.6 Test `/validate run <artifact-id>` passes valid artifact.
- [x] 9.7 Test validation fails missing lineage.
- [x] 9.8 Test validation fails missing caveats.
- [x] 9.9 Test `/deploy verify` requires validation evidence.
- [x] 9.10 Test `/deploy promote` promotes only research artifact.
- [x] 9.11 Test `/deploy rollback` records rollback.
- [x] 9.12 Test read-only boundary blocks execution-like deploy requests.

## 10. Documentation and validation

- [x] 10.1 Add closed-loop repair architecture doc.
- [x] 10.2 Document repair bundle schema.
- [x] 10.3 Document validation gate.
- [x] 10.4 Document deploy log semantics for research artifacts.
- [x] 10.5 Document read-only research boundary for repair/deploy.
- [ ] 10.6 Run `make test-vnalpha`.
- [ ] 10.7 Run `make lint-vnalpha`.
- [x] 10.8 Run `make verify-r4`.
- [x] 10.9 Run `openstock-verify --ci`.
- [ ] 10.10 Attach validation evidence to PR.
